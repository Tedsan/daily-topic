.PHONY: help install test lint format clean dev deps update

# デフォルトターゲット
help:
	@echo "Daily Topic システム - Make コマンド"
	@echo ""
	@echo "利用可能なコマンド:"
	@echo "  install     - 依存関係をインストール"
	@echo "  dev         - 開発用の依存関係をインストール"
	@echo "  test        - テストを実行"
	@echo "  test-unit   - ユニットテストのみ実行"
	@echo "  test-integration - 統合テストのみ実行"
	@echo "  test-e2e    - E2Eテストのみ実行"
	@echo "  coverage    - カバレッジレポートを生成"
	@echo "  lint        - コードをlint"
	@echo "  format      - コードをフォーマット"
	@echo "  type-check  - 型チェックを実行"
	@echo "  clean       - キャッシュファイルを削除"
	@echo "  deps        - 依存関係を更新"
	@echo "  pre-commit  - pre-commitフックを実行"
	@echo "  run         - メインプログラムを実行"

# 依存関係のインストール
install:
	poetry install --only=main

# 開発用依存関係のインストール
dev:
	poetry install
	poetry run pre-commit install

# テスト実行
test:
	poetry run pytest --cov=src --cov-report=html --cov-report=term-missing

# ユニットテストのみ
test-unit:
	poetry run pytest tests/unit/ -v

# 統合テストのみ
test-integration:
	poetry run pytest tests/integration/ -v

# E2Eテストのみ
test-e2e:
	poetry run pytest tests/e2e/ -v

# カバレッジレポート生成
coverage:
	poetry run pytest --cov=src --cov-report=html
	@echo "カバレッジレポートが htmlcov/index.html に生成されました"

# Lint
lint:
	poetry run ruff check .
	poetry run flake8 src/ tests/

# フォーマット
format:
	poetry run black .
	poetry run isort .
	poetry run ruff check --fix .

# 型チェック
type-check:
	poetry run mypy src/

# 品質チェック (lint + type-check)
quality: lint type-check

# キャッシュファイルの削除
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf dist/
	rm -rf build/

# 依存関係の更新
deps:
	poetry update

# pre-commitフックの実行
pre-commit:
	poetry run pre-commit run --all-files

# メインプログラムの実行
run:
	poetry run python src/main.py

# 開発サーバーの起動（将来的にAPI化する場合）
serve:
	poetry run python src/main.py --serve

# Docker関連（将来的に追加）
docker-build:
	docker build -t daily-topic .

docker-run:
	docker run --env-file .env daily-topic

# CI/CD関連
ci-test:
	poetry run pytest --cov=src --cov-report=xml --cov-fail-under=80

ci-lint:
	poetry run ruff check .
	poetry run black --check .
	poetry run isort --check-only .
	poetry run mypy src/

# 統計情報の表示
stats:
	@echo "プロジェクト統計:"
	@echo "  Python ファイル数: $$(find src/ -name '*.py' | wc -l)"
	@echo "  テストファイル数: $$(find tests/ -name '*.py' | wc -l)"
	@echo "  総行数: $$(find src/ tests/ -name '*.py' -exec wc -l {} + | tail -1)"

# 開発環境のリセット
reset: clean
	rm -rf .venv/
	poetry install
	poetry run pre-commit install

# 本番環境用のビルド
build:
	poetry build

# パッケージのインストール
install-package:
	pip install dist/*.whl
