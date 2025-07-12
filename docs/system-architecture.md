# Daily Topic System Architecture

## Overview

Daily Topic Systemは、SlackのRSSフィードから記事を取得し、Claude Code SDKを使用して要約を生成し、カテゴリ分類してSlackに投稿するシステムです。

## System Flow

### 1. Overall Process Flow

```mermaid
flowchart TD
    A[Start: Daily Topic System] --> B[Initialize Configuration]
    B --> C[Setup GitHub Actions Environment]
    C --> D[Get RSS Feed Messages from Slack]
    D --> E[Extract URLs from Messages]
    E --> F[Fetch Content from URLs]
    F --> G[Parse HTML to Markdown]
    G --> H[Categorize Articles]
    H --> I{Has Summarizable Categories?}
    I -->|Yes| J[Generate Summaries with Claude]
    I -->|No| K[Create Report with Other Articles Only]
    J --> L[Create Complete Report]
    K --> M[Post to Slack]
    L --> M
    M --> N[Save Statistics]
    N --> O[End]
```

### 2. RSS Feed Processing

```mermaid
flowchart TD
    A[RSS Feed Processing] --> B[Connect to Slack API]
    B --> C[Get Channel ID for 'rss-feed']
    C --> D[Calculate Time Range<br/>Current Time - 24 hours]
    D --> E[Fetch Messages from Channel]
    E --> F[Filter Messages by Time Range]
    F --> G[Extract URLs using Regex]
    G --> H{URLs Found?}
    H -->|Yes| I[Return List of URLs]
    H -->|No| J[Return Empty List]
    I --> K[End]
    J --> K
```

### 3. Content Processing Pipeline

```mermaid
flowchart TD
    A[Content Processing] --> B[For Each URL]
    B --> C[Fetch HTML Content]
    C --> D{HTTP Request Success?}
    D -->|No| E[Skip URL]
    D -->|Yes| F[Parse HTML with BeautifulSoup]
    F --> G[Extract Text Content]
    G --> H[Convert to Markdown]
    H --> I[Create Article Metadata]
    I --> J[Add to Article List]
    J --> K{More URLs?}
    K -->|Yes| B
    K -->|No| L[Return Article List]
    E --> K
    L --> M[End]
```

### 4. Article Categorization Algorithm

```mermaid
flowchart TD
    A[Article Categorization] --> B[For Each Article]
    B --> C[Extract Keywords from Content]
    C --> D[Calculate Category Scores]
    D --> E[Score Categories C1-C5]
    E --> F{Any Score > Threshold?}
    F -->|Yes| G[Assign Best Matching Category]
    F -->|No| H[Assign Category C6 'Other']
    G --> I[Add to Categorized Articles]
    H --> J[Add to Other Articles]
    I --> K{More Articles?}
    J --> K
    K -->|Yes| B
    K -->|No| L[Return Categorized Results]
    L --> M[End]
```

### 5. Category Scoring Details

```mermaid
flowchart TD
    A[Category Scoring] --> B[Initialize Scores for C1-C5]
    B --> C[For Each Category]
    C --> D[Get Category Keywords]
    D --> E[Count Keyword Matches in Article]
    E --> F[Calculate Score:<br/>matches / total_keywords]
    F --> G[Store Score]
    G --> H{More Categories?}
    H -->|Yes| C
    H -->|No| I[Find Maximum Score]
    I --> J{Score >= 0.3?}
    J -->|Yes| K[Return Best Category]
    J -->|No| L[Return 'C6' Other]
    K --> M[End]
    L --> M
```

### 6. Summary Generation with Claude

```mermaid
flowchart TD
    A[Summary Generation] --> B[For Each Categorized Article Group]
    B --> C[Combine Article Contents]
    C --> D[Create System Prompt for Category]
    D --> E[Create User Prompt with Content]
    E --> F[Call Claude Code SDK]
    F --> G{Claude Response OK?}
    G -->|Yes| H[Parse JSON Response]
    G -->|No| I[Log Error & Skip]
    H --> J[Validate Response Format]
    J --> K{Valid JSON?}
    K -->|Yes| L[Extract Summary Data]
    K -->|No| M[Use Fallback Summary]
    L --> N[Calculate Token Usage & Cost]
    M --> N
    N --> O[Add to Summary List]
    O --> P{More Categories?}
    P -->|Yes| B
    P -->|No| Q[Return Summary List]
    I --> P
    Q --> R[End]
```

### 7. Slack Message Posting

```mermaid
flowchart TD
    A[Slack Message Posting] --> B[Create Daily Topic Report]
    B --> C[Build Block Kit Message]
    C --> D[Add Date Header]
    D --> E[Add Theme Header]
    E --> F{Has Summaries?}
    F -->|Yes| G[Add Summary Sections]
    F -->|No| H[Add 'No Summaries' Message]
    G --> I{Has Other Articles?}
    H --> I
    I -->|Yes| J[Add Other Articles Section]
    I -->|No| K[Add Footer with Stats]
    J --> K
    K --> L[Post to Slack Channel]
    L --> M{Post Success?}
    M -->|Yes| N[Log Success]
    M -->|No| O[Log Error & Retry]
    N --> P[End]
    O --> P
```

### 8. Error Handling Flow

```mermaid
flowchart TD
    A[Error Occurs] --> B{Error Type?}
    B -->|Slack API Error| C[Retry with Exponential Backoff]
    B -->|Claude API Error| D[Log Error & Use Fallback]
    B -->|Network Error| E[Retry with Timeout]
    B -->|Configuration Error| F[Exit with Error Message]
    C --> G{Retry Success?}
    D --> H[Continue with Partial Results]
    E --> I{Retry Success?}
    F --> J[Send Error to Slack]
    G -->|Yes| K[Continue Processing]
    G -->|No| L[Log Final Error]
    H --> K
    I -->|Yes| K
    I -->|No| L
    J --> M[Exit]
    K --> N[End]
    L --> O[Send Error Notification]
    O --> M
```

## Category Definitions

| Category | Label                    | Keywords                                                                               |
| -------- | ------------------------ | -------------------------------------------------------------------------------------- |
| C1       | Software-Defined Vehicle | SDV, AUTOSAR, Adaptive AUTOSAR, 車載ソフト                                             |
| C2       | Industrial IoT & Edge    | Industrial IoT, IIoT, スマートファクトリー, Edge Computing                             |
| C3       | Industrial Protocols     | MQTT, OPC UA, OPC UA FX, open62541, TSN, openPLC                                       |
| C4       | Generative AI Tech       | Gemini CLI, Gemini 1.5, Claude 3, Claude Code, OpenAI, Anthropic, Mistral AI, DeepMind |
| C5       | Gen-AI Use Cases         | 生成AI 活用事例, LLM ユースケース, RAG, AI agent, 導入事例, Case Study                 |
| C6       | Other                    | 上記いずれにも当てはまらない場合                                                       |

## Key Algorithms

### 1. URL Extraction from Slack Messages

```python
URL_PATTERN = r'https?://[^\s<>"{}|\\^`[\]]+(?:[^\s<>"{}|\\^`[\].,;:!?)])'
urls = re.findall(URL_PATTERN, message_text)
```

### 2. Category Scoring Algorithm

```python
def calculate_category_score(content: str, keywords: List[str]) -> float:
    content_lower = content.lower()
    matches = sum(1 for keyword in keywords if keyword.lower() in content_lower)
    return matches / len(keywords) if keywords else 0.0
```

### 3. Content Length Optimization

- HTMLコンテンツ: 最大20,000文字
- Claude APIプロンプト: 最大3,000文字
- 要約結果: 最大500文字

### 4. Rate Limiting

- Slack API: 1秒あたり1リクエスト
- Claude API: デフォルト制限に従う
- HTTP取得: 並列処理でタイムアウト10秒

## Configuration

### Environment Variables

- `SLACK_BOT_TOKEN`: Slack Bot Token
- `ANTHROPIC_API_KEY`: Claude API Key
- `RSS_FEED_CHANNEL`: RSS取得チャネル名（デフォルト: "rss-feed"）
- `DAILY_TOPIC_CHANNEL`: 投稿先チャネル名（デフォルト: "daily-topic"）
- `LOOKBACK_HOURS`: 取得対象時間（デフォルト: 24時間）

### GitHub Actions Configuration

- **スケジュール**: 毎日08:00 JST（23:00 UTC）
- **手動実行**: カテゴリ指定・時間指定可能
- **タイムアウト**: 5分
- **エラー通知**: Slackに自動通知

## Performance Characteristics

- **処理時間**: 平均2-3分（記事数により変動）
- **メモリ使用量**: 約100-200MB
- **API呼び出し回数**:
  - Slack API: 3-5回
  - Claude API: カテゴリ数分（最大5回）
  - HTTP取得: URL数分

## Monitoring & Logging

- **ログレベル**: INFO（本番）、DEBUG（開発）
- **統計情報**: `stats/` ディレクトリに保存
- **エラー追跡**: Slackチャネルに通知
- **GitHub Actions**: ワークフロー実行履歴で監視
