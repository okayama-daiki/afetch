# afetch v1.0.0 要求仕様書

## 1. 文書情報
- **文書名**: afetch v1.0.0 要求仕様書
- **対象製品**: `afetch` ライブラリ
- **対象バージョン**: v1.0.0（計画中）
- **作成日**: YYYY-MM-DD（確定版リリース時に更新）
- **読者対象**: 開発者、テスター、プロダクトオーナー、運用担当者
- **目的**: v1.0.0 に向けた機能・非機能要求、設計指針、制約条件を明文化し、実装・テスト・運用の基準を提供する

## 2. 背景と目的
`afetch` は必要最低限の機能を備えた非同期 HTTP クライアントを提供してきたが、現行バージョンでは GET テキスト取得に限定され、ログ出力、細かな例外制御、タイムアウト、リクエストカスタマイズといった機能が不足している。v1.0.0 ではリクエストファーストな API へ進化させ、柔軟な構成と観測可能性を備えたライブラリへ拡張する。

## 3. 用語定義
- **Fetcher**: 本ライブラリが提供する非同期 HTTP クライアントクラス。
- **request()**: 任意の HTTP メソッド・パラメータを受け付ける新しい汎用 API。
- **fetch()**: 従来のテキストレスポンス取得 API。内部的に request() を利用し後方互換を維持。
- **RequestOptions**: 個別リクエスト向けの設定を保持するデータクラス。
- **ResponseHandler**: レスポンス処理戦略を表現するプロトコルまたはコールバック。
- **FetcherConfig**: Fetcher 全体のデフォルト構成を定義する設定データクラス。
- **FetcherError**: 新設する例外階層のルートクラス。
- **構造化ログ**: JSON など機械可読な形式でログを出力する仕組み。

## 4. システム概要
- Fetcher は `async with` を用いるコンテキストマネージャとして提供する。
- 内部コンポーネントを「セッション管理」「レート制限」「リクエスト実行」「レスポンス処理」に分割し、可観測性（ログ、メトリクス）とエラーハンドリングを一元化する。
- request() を中核 API とし、fetch()/fetch_all() は request() をラップする上位互換 API とする。

## 5. 想定利用者
- Web API クライアントやスクレイピング、データ取得パイプラインを実装する Python エンジニア。
- サービス連携やバッチ処理で安定した HTTP 通信を必要とするバックエンド開発者。
- 通信監視やエラーレポートを行いたい SRE/運用担当。

## 6. 前提・制約条件
1. **実行環境**
   - Python 3.12 以上（3.13, 3.14 を公式サポート対象）
   - asyncio イベントループが動作していること
2. **依存パッケージ**
   - `aiohttp`（HTTP クライアント）
   - `aiohttp-client-cache`（キャッシュ機構、filesystem 以外のバックエンドはオプション）
   - `aiohttp-retry`（再試行ロジック）
   - `aiolimiter`（レート制限）
   - 追加予定: `structlog` などのログ依存は検討中。標準 logging 互換インタフェースで抽象化し、直接依存は避ける。
3. **互換性**
   - v0.x 系利用者との後方互換を維持する（デフォルト挙動、公開 API 名、設定項目の意味）。
   - Breaking change が必要な場合は非推奨期間を設ける。
4. **ネットワーク**
   - 外部 HTTP 通信が可能な環境を前提とする。
5. **ハードウェア**
   - 特別な制約なし。キャッシュディスク容量は利用規模に依存。

## 7. 機能要求 (Functional Requirements)

### FR-1 汎用 request() API
- `Fetcher.request(method, url, options)` を新設し、任意メソッド・ペイロード・ヘッダー・タイムアウト・レスポンス処理を受け付ける。
- `RequestOptions` で以下を指定可能とする:
  - HTTP メソッド（文字列）
  - ヘッダー（dict）
  - クエリパラメータ・URL 変換
  - ボディ（bytes/str/JSON/フォームデータ）
  - タイムアウト（秒）
  - レスポンスハンドラ
  - キャッシュ利用可否
  - リトライ制御（回数、エラー種別オーバーライド）
  - Rate limiter スキップ指定（例: POST はキャッシュ不可だがレート制御は適用）
- リクエスト毎に config のデフォルト値とオプションを deterministic にマージする（ヘッダーは大文字小文字無視で統合）。

### FR-2 fetch()/fetch_all() 後方互換
- `fetch()` は内部で `request()` を呼び出し、デフォルトで `GET` + テキストレスポンスを返す挙動を維持する。
- `fetch_all()` は `Iterable[RequestOptions | URL | str]` を受け付ける。URL/str の場合はデフォルトオプションに変換。
- `fetch_all()` に `return_exceptions` フラグを導入し、True なら例外を結果リストに格納、False なら最初の例外を即座に送出する。
- 既存の `fetch_all(urls: Iterable[str | URL]) -> list[str]` シグネチャを維持しつつ拡張引数を追加する（位置引数互換性に留意）。

### FR-3 リクエストカスタマイズ
- デフォルトヘッダーやタイムアウト値は `FetcherConfig` に設定し、RequestOptions で上書き可能。
- ヘッダー統合ロジックは case-insensitive で、RequestOptions の指定が優先される。
- `FetcherConfig` に `default_query_params`、`default_timeout`, `default_response_handler`, `default_headers` を追加する。

### FR-4 レスポンスハンドリング
- `ResponseHandler` プロトコル（`Protocol`）を定義し、同期・非同期両方を許容する（open question の検討結果: 同期ハンドラを async 化して実行、必要に応じて await）。
- 標準提供ハンドラ:
  - `TextResponseHandler`（str）
  - `JsonResponseHandler`（dict/list）
  - `BytesResponseHandler`（bytes）
  - `RawResponseHandler`（`aiohttp.ClientResponse` を返却）
- `fetch()` のデフォルトは `TextResponseHandler`。
- ハンドラは status code チェック後に実行し、例外は `FetcherError` でラップする。

### FR-5 タイムアウト管理
- `FetcherConfig` に `default_timeout`（aiohttp の `ClientTimeout` 相当）を追加。
- RequestOptions で per-request timeout を指定可能。
- Timeout 発生時は `FetcherTimeoutError` を送出し、元例外を `__cause__` に保持。

### FR-6 構造化ログ
- `FetcherConfig` に logger（logging.Logger 互換）または callable を注入できるようにする。未指定時はモジュールロガーを使用。
- ログ出力ポイント:
  - リクエスト開始/終了（メソッド、URL、ステータス、所要時間）
  - レートリミット待機（ドメイン、待機時間）
  - キャッシュヒット/ミス
  - リトライ試行（回数、理由、次回待機時間）
  - 例外発生（FetcherError 種別、元例外情報）
- ログは構造化（dict ベース）で記録し、ロガーのフォーマッタ設定に依存せず情報を持てる形にする。

### FR-7 例外階層
- `FetcherError` を基底クラスとし、主な派生:
  - `FetcherTimeoutError`
  - `FetcherRateLimitError`
  - `FetcherResponseError`（HTTP ステータス異常）
  - `FetcherRequestError`（通信エラー/接続失敗）
  - `FetcherConfigurationError`（設定不備）
- aiohttp / aiohttp_retry の例外を捕捉し、FetcherError で包んでから送出する。`__cause__` に元例外、`context` 属性にリクエストメタ情報（URL、メソッド、試行回数など）を保持。
- `return_exceptions=True` 時はこれらの FetcherError インスタンスを返却。

### FR-8 レート制限とドメイン解決強化
- ドメイン解析は `yarl.URL` と `urllib.parse` の両方を用いて堅牢化し、ポート指定や国際化ドメインを扱う。
- ドメインが解析できない場合は `FetcherConfigurationError` を送出。
- レートリミッターはドメインごとに生成し、キャッシュヒット時は待機をスキップする既存挙動を維持。
- RequestOptions でレートリミットを無効化するフラグを提供する（例: 内部通信やヘルスチェック用途）。

### FR-9 キャッシュ制御
- `FetcherConfig` および RequestOptions に `cache_enabled` フラグを提供し、リクエスト単位でキャッシュ利用を切り替え可能。
- キャッシュ無効時は backend に `expire_after=0` など適切な設定を行うか、キャッシュバイパスのフックを実装する。
- キャッシュキー生成はメソッド・URL・ヘッダーの可変要素を考慮できるよう拡張（POST など非キャッシュ対象はデフォルトで無効）。

### FR-10 fetch_all 並列制御
- `fetch_all` に任意の `asyncio.Semaphore` を注入できるよう `FetcherConfig` に `concurrency_limit` を追加（None の場合は制限なし）。
- レートリミッターとの相互作用を考慮し、Semaphore 後にレートリミットを適用する順序とする。

## 8. 非機能要求 (Non-Functional Requirements)

### NFR-1 パフォーマンス
- request()/fetch_all() はイベントループをブロックしない。
- 追加ログやエラーハンドリングは O(1) の追加コストに抑える。
- キャッシュヒット時は v0.x と同等のパフォーマンスを維持。
- 新規構造が従来の並列性能を劣化させないようベンチマークを実施。

### NFR-2 信頼性
- リトライは指数バックオフ（`aiohttp_retry.ExponentialRetry`）を継続利用。
- 例外階層により失敗原因を判別可能にする。
- タイムアウト、接続エラー、HTTP エラーなど各ケースで期待通りの例外が送出されることをテストで保証。

### NFR-3 観測可能性
- ログは JSON フレンドリーな dict 構造で emit する。
- 後続のメトリクス導入を想定し、ログフィールドに `elapsed_ms`, `attempt`, `rate_limit_wait_ms`, `cache_hit` 等を含める。
- 必要に応じて利用者がメトリクスフックを差し込める拡張ポイントを `FetcherConfig` に提供（例: コールバック）。

### NFR-4 保守性・拡張性
- 新規 RequestOptions/ResponseHandler 体系は明確な型ヒントとドキュメントを備える。
- 内部モジュールを小さなコンポーネントへ分割（例: `_rate_limiter.py`, `_request_executor.py`）し、単体テストを容易にする。
- `FetcherConfig` に追加フィールドを設ける際はデフォルト値で後方互換を維持。

### NFR-5 移植性
- Python 標準＋既存依存ライブラリの範囲で完結し、OS 依存機構を導入しない。
- ログ実装は標準 logging をベースにし、外部ログライブラリへの依存はオプション扱い。

### NFR-6 品質保証
- Lint（ruff）、静的解析（basedpyright strict）を継続。
- テストカバレッジを v0.x より向上させる（目標: 90%以上、クリティカル経路 100%）。
- CI ではユニットテスト、タイプチェック、フォーマッタチェック、ドキュメントビルドを実行。

## 9. 外部インタフェース要求

### 9.1 API
- `Fetcher` クラス
  - `__init__(config: FetcherConfig | None = None)`
  - `async def request(self, method: str, url: StrOrURL, options: RequestOptions | None = None) -> ResponseType`
  - `async def fetch(self, url: StrOrURL, *, response_handler: ResponseHandler | None = None, options: RequestOptions | None = None) -> str`
  - `async def fetch_all(self, requests: Iterable[RequestInput], *, return_exceptions: bool = False, response_handler: ResponseHandler | None = None) -> list[Any]`
  - `async def __aenter__() -> Fetcher`
  - `async def __aexit__(...) -> None`
- `FetcherConfig`
  - `max_rate_per_domain: int`
  - `time_period_per_domain: float`
  - `retry_attempts: int`
  - `cache_backend: CacheBackend | None`
  - `cache_enabled: bool`
  - `default_headers: Mapping[str, str]`
  - `default_query_params: Mapping[str, str]`
  - `default_timeout: float | ClientTimeout | None`
  - `default_response_handler: ResponseHandler`
  - `logger: LoggerLike | None`
  - `concurrency_limit: int | None`
  - `return_exceptions: bool`
  - `retry_for_exceptions: tuple[type[BaseException], ...] | None`
- `RequestOptions`
  - `method: str | None`
  - `headers: Mapping[str, str] | None`
  - `query_params: Mapping[str, str] | None`
  - `json: Any | None`
  - `data: Any | None`
  - `timeout: float | ClientTimeout | None`
  - `response_handler: ResponseHandler | None`
  - `cache_enabled: bool | None`
  - `retry_attempts: int | None`
  - `retry_for_exceptions: tuple[type[BaseException], ...] | None`
  - `skip_rate_limit: bool | None`
  - `context: dict[str, Any]`（ログ補強用メタデータ）

### 9.2 CLI/GUI
- 提供しない。

### 9.3 ファイル/リソース
- キャッシュは `.afetch_cache/` をデフォルトとし、config で変更可能。
- ログ出力先は利用者の logger 設定に準拠。

## 10. エラーハンドリング要求
- request()/fetch()/fetch_all() で発生するすべての例外は FetcherError 階層に正規化する。
- リトライ失敗時は最終例外を cause に保持しつつ FetcherError を送出。
- 設定ミス（不正 URL、メソッド未指定など）は即座に `FetcherConfigurationError`。
- `return_exceptions=True` での fetch_all は結果リスト内に FetcherError を収容。
- `fetch_all` のデフォルトは最初の例外送出（v0.x と同様）。

## 11. ログ・監視要求
- ログフィールド例:
  - `event`: `"request.start"`, `"request.success"`, `"request.error"`, `"retry.schedule"`, `"cache.hit"`, `"rate_limit.wait"`
  - `method`, `url`, `status`, `elapsed_ms`, `attempt`, `timeout`, `cache_hit`, `retry_count`, `error_type`
- ロガーは DEBUG/INFO レベルを使い分け、重大エラーは WARNING/ERROR で出力。
- 今後のメトリクス連携を想定し、`FetcherConfig` にフック関数（例: `metrics_hook(event: str, payload: dict)`）を追加するか検討（後続タスク）。

## 12. 品質管理・テスト戦略
- **ユニットテスト**
  - RequestOptions のマージロジック（ヘッダー、タイムアウト、キャッシュ）
  - 各 ResponseHandler の出力/例外
  - request() のメソッド/ボディ/ヘッダー処理
  - レートリミット待機とログ出力
  - タイムアウトと FetcherTimeoutError
  - FetcherError 派生クラスの cause/context
- **統合テスト**
  - キャッシュ無効化・有効化切替
  - fetch_all の concurrency_limit と return_exceptions
  - 例外発生時ログが構造化されるか（ロガーモック）
  - リトライ経路（失敗→成功、失敗→失敗）
  - 非 GET メソッド（POST/PUT/DELETE）の挙動
- **ドキュメントテスト**
  - README のサンプルコードを doctest で検証。
- **CI**
  - lint、type check、unit/integration test、coverage、ドキュメントビルド。
- **カバレッジ目標**
  - ステートメントカバレッジ 90%
  - クリティカルパス（レート制限、リトライ、例外ラップ）100%

## 13. ドキュメント & ロールアウト
- README 更新:
  - request() の使用例（メソッド指定、ヘッダー、タイムアウト、レスポンスハンドラ）
  - fetch_all の RequestOptions 対応例
  - ログ出力と例外階層の説明
- `docs/` 配下に詳細設計ドキュメント（アーキテクチャ説明、ResponseHandler カタログ、エラーマップ）を追加。
- CHANGELOG に v1.0.0 エントリを作成（機能追加、非互換なし、設定項目追加を明記）。
- 必要に応じて ADR を作成し、request ファーストアーキテクチャへの移行理由を記録。
- リリース候補を段階的に公開（α → β → RC）し、コミュニティフィードバックを受ける。

## 14. 非目標 (Non-Goals)
- 既存依存ライブラリ（aiohttp/aiohttp_retry/aiolimiter）を独自実装に置き換えること。
- ストリーミングレスポンスや WebSocket サポートの提供。
- デフォルト挙動を非互換に変更すること（例: fetch() の戻り値型変更）。

## 15. 代替案
- request() を追加せず fetch()/fetch_all のキーワード引数にオプションを詰め込む案も検討されたが、ログ/例外/レスポンス処理の一貫制御が困難になるため不採用。

## 16. 影響・リスク
- API 表面積拡大に伴うバグ増加 → テスト範囲を広げ、ステージング段階で実運用ケースを検証。
- デフォルト設定変更による既存利用者の影響 → デフォルト値は従来と同一に保ち、ドキュメントで差分を明示。
- ログ出力過多によるパフォーマンス劣化 → ログレベル/サンプリング設定や無効化手段を提供。

## 17. オープン課題
1. リトライポリシーをユーザー設定可能にする範囲（指数バックオフパラメータなど）をどこまで公開するか。
2. ResponseHandler の同期/非同期両対応をどのように実装・ドキュメント化するか。
3. レートリミット待機時間の外部計測手段（メトリクス API vs. ログのみ）をどう設計するか。
4. 構造化ログのフォーマット標準（JSON 並列化）を提供するか。

## 18. 決定チェックリスト
- [ ] ステークホルダーの承認
- [ ] リスク評価の確認
- [ ] 後続タスク（ADR、メトリクス拡張、ドキュメント更新、ベンチマーク）の課題化
