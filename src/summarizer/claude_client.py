"""Claude APIクライアント"""
import json
from typing import Optional

from claude_code_sdk import ClaudeCodeOptions, query

from src.config import get_config
from src.utils.error_handler import ClaudeAPIError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ClaudeClient:
    """Claude APIクライアント"""

    def __init__(self, api_key: Optional[str] = None):
        config = get_config()
        self.api_key = api_key or config.claude.api_key

        # 設定
        self.model = config.claude.model
        self.max_tokens = config.claude.max_tokens
        self.temperature = config.claude.temperature

        # コスト計算用
        self.cost_per_input_token = config.claude.cost_per_input_token
        self.cost_per_output_token = config.claude.cost_per_output_token

        logger.info(f"Claude client initialized with model: {self.model}")

    async def _call_claude_code_sdk(self, prompt: str, max_turns: int = 1) -> dict:
        """Claude Code SDK経由でAPI呼び出し"""
        try:
            options = ClaudeCodeOptions(max_turns=max_turns)

            # Claude Code SDKを使用して要約生成
            messages = []
            assistant_message = None
            result_message = None

            async for message in query(prompt=prompt, options=options):
                messages.append(message)
                logger.debug(f"Received message type: {type(message)}")

                # AssistantMessageとResultMessageを特定
                if hasattr(message, "content") and isinstance(message.content, list):
                    assistant_message = message
                elif hasattr(message, "result") and hasattr(message, "usage"):
                    result_message = message

            if not messages:
                raise ClaudeAPIError("No response from Claude Code SDK")

            # コンテンツを抽出（AssistantMessageから）
            content = ""
            if assistant_message and hasattr(assistant_message, "content"):
                # content is a list of TextBlock objects
                text_parts = []
                for block in assistant_message.content:
                    if hasattr(block, "text"):
                        text_parts.append(block.text)
                content = "".join(text_parts)
                logger.info(
                    f"Extracted content from AssistantMessage: {content[:100]}..."
                )

            # フォールバック：ResultMessageのresultを使用
            if not content and result_message and hasattr(result_message, "result"):
                content = result_message.result
                logger.info(f"Using result from ResultMessage: {content[:100]}...")

            if not content:
                logger.warning("No content found in Claude response")
                content = "要約の生成に失敗しました。"

            # 使用量情報を取得（ResultMessageから）
            usage_info = {"input_tokens": 0, "output_tokens": 0}
            if (
                result_message
                and hasattr(result_message, "usage")
                and result_message.usage
            ):
                usage = result_message.usage
                usage_info = {
                    "input_tokens": usage.get("input_tokens", 0) if usage else 0,
                    "output_tokens": usage.get("output_tokens", 0) if usage else 0,
                }
                logger.info(f"Token usage: {usage_info}")

            return {"content": content, "usage": usage_info}

        except Exception as e:
            logger.error(f"Claude Code SDK error: {e}")
            raise ClaudeAPIError(f"Claude Code SDK error: {e}")

    async def generate_summary(
        self,
        content: str,
        category: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> dict:
        """要約を生成

        Returns:
            dict: {
                "category": str,
                "summary": str,
                "confidence": float,
                "key_points": List[str],
                "usage": {
                    "input_tokens": int,
                    "output_tokens": int,
                    "cost_usd": float
                }
            }
        """
        try:
            # デフォルトのシステムプロンプト
            if system_prompt is None:
                system_prompt = self._create_default_system_prompt(category)

            # ユーザープロンプト
            user_prompt = self._create_user_prompt(content, category)

            # 完全なプロンプト（システム + ユーザー）
            full_prompt = f"{system_prompt}\n\n{user_prompt}"

            # Claude Code SDK経由でAPI呼び出し
            response = await self._call_claude_code_sdk(full_prompt)

            # レスポンスのパース
            result = self._parse_claude_response(response, category)

            logger.info(
                f"Summary generated for category {category}: "
                f"{result['usage']['input_tokens']} input tokens, "
                f"{result['usage']['output_tokens']} output tokens, "
                f"${result['usage']['cost_usd']:.4f}"
            )

            return result

        except ClaudeAPIError:
            raise
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            raise ClaudeAPIError(f"Failed to generate summary: {e}")

    def _create_default_system_prompt(self, category: str) -> str:
        """デフォルトのシステムプロンプトを作成"""
        from src.models import CATEGORY_INFO

        category_info = CATEGORY_INFO.get(category, {})
        category_label = category_info.get("label", "Unknown")
        keywords = category_info.get("keywords", [])

        system_prompt = f"""あなたは技術記事の要約を専門とするAIアシスタントです。

カテゴリ: {category} ({category_label})
関連キーワード: {', '.join(keywords)}

以下の要件に従って要約を生成してください：

1. 500文字以内で要約を作成
2. 技術的な内容を正確に伝える
3. 重要なポイントを3-5個抽出
4. 信頼度（0.0-1.0）を評価
5. 必ず以下のJSON形式で出力：

{{
    "category": "{category}",
    "summary": "要約内容（500文字以内）",
    "confidence": 0.8,
    "key_points": ["ポイント1", "ポイント2", "ポイント3"]
}}

JSON以外の文字は出力しないでください。"""

        return system_prompt

    def _create_user_prompt(self, content: str, category: str) -> str:
        """ユーザープロンプトを作成"""
        # コンテンツを適切な長さに切り詰め
        max_content_length = 3000  # トークン制限を考慮
        if len(content) > max_content_length:
            content = content[:max_content_length] + "..."

        return f"""以下の記事を{category}カテゴリの観点から要約してください：

{content}

上記の記事を500文字以内で要約し、指定されたJSON形式で出力してください。"""

    def _parse_claude_response(self, response: dict, expected_category: str) -> dict:
        """レスポンスをパース"""
        try:
            # レスポンステキストを取得
            if not response.get("content"):
                raise ClaudeAPIError("Empty response from Claude Code SDK")

            response_text = response["content"]

            # JSONパース
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError:
                # JSONパースに失敗した場合、テキストから抽出を試行
                logger.warning(
                    "Failed to parse JSON response, attempting text extraction"
                )
                result = self._extract_json_from_text(response_text)

            # 基本的な検証
            if not isinstance(result, dict):
                raise ClaudeAPIError("Response is not a valid JSON object")

            # 必須フィールドの確認
            required_fields = ["category", "summary"]
            for field in required_fields:
                if field not in result:
                    raise ClaudeAPIError(f"Missing required field: {field}")

            # カテゴリの確認
            if result["category"] != expected_category:
                logger.warning(
                    f"Category mismatch: expected {expected_category}, "
                    f"got {result['category']}"
                )
                result["category"] = expected_category

            # 要約の長さ確認
            if len(result["summary"]) > 500:
                logger.warning("Summary exceeds 500 characters, truncating")
                result["summary"] = result["summary"][:497] + "..."

            # デフォルト値の設定
            if "confidence" not in result:
                result["confidence"] = 0.7
            if "key_points" not in result:
                result["key_points"] = []

            # 使用量情報の追加
            usage = response.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            result["usage"] = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": self._calculate_cost(input_tokens, output_tokens),
            }

            return result

        except Exception as e:
            logger.error(f"Error parsing Claude response: {e}")
            raise ClaudeAPIError(f"Failed to parse response: {e}")

    def _extract_json_from_text(self, text: str) -> dict:
        """テキストからJSONを抽出（フォールバック）"""
        import re

        # JSON部分を抽出
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        # 抽出に失敗した場合、最低限の構造を返す
        return {
            "category": "C6",
            "summary": "要約の生成に失敗しました。",
            "confidence": 0.0,
            "key_points": [],
        }

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """コストを計算"""
        input_cost = input_tokens * self.cost_per_input_token
        output_cost = output_tokens * self.cost_per_output_token
        return input_cost + output_cost

    async def test_connection(self) -> bool:
        """接続テスト"""
        try:
            test_response = await self.generate_summary(
                content="This is a test article about technology.",
                category="C6",
                system_prompt='Test system prompt. Respond with a simple JSON: {"category": "C6", "summary": "Test summary", "confidence": 0.9}',
            )

            if test_response.get("category") == "C6":
                logger.info("Claude connection test successful")
                return True
            else:
                logger.error("Claude connection test failed: invalid response")
                return False

        except Exception as e:
            logger.error(f"Claude connection test failed: {e}")
            return False
