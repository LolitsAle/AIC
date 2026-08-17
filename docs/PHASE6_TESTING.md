# Phase 6 - Hướng Dẫn Test Query Planner Và Reranker

Phase 6 là **opt-in**. Query planner là rule-based local, không gọi LLM/API. Reranker chỉ chạy trên Top-N video đã qua candidate generation và RRF, không chạy trên toàn dataset.

## 1. Test tự động

```bash
python -m compileall -q src tools tests
python -m pytest tests/test_query_planner.py tests/test_reranking.py tests/test_phase6_ui_static.py -q
python -m pytest tests/test_hybrid_candidates.py tests/test_hybrid_ranking.py tests/test_structured_api.py -q
python -m pytest tests -q
git diff --check
```

## 2. Dò query plan bằng tay

Khởi động UI như Phase 5 rồi gọi:

```bash
curl -G -s http://127.0.0.1:8765/api/query-plan \
  --data-urlencode 'q=người cầm điện thoại, sau đó nói "xin chào"'
```

Kiểm tra:

- `recommended_modalities` có `clip`, `objects`, `asr`.
- `objects` có `person`, `phone`.
- `temporal_hints` có `sau đó`.
- `variants` có câu gốc và phrase trong dấu ngoặc kép.
- `version` bắt đầu bằng `phase6-rule-planner`.

Các query dò tối thiểu:

| Query | Modality mong đợi |
|---|---|
| `người cầm điện thoại` | CLIP + objects |
| `biển hiệu chữ Samsung` | CLIP + OCR |
| `người nói xin chào quý vị` | CLIP + ASR |
| `người mặc áo đỏ` | CLIP + attributes |
| `video của kênh Tuổi Trẻ` | CLIP + metadata |
| `đi vào cửa hàng, sau đó cầm điện thoại` | CLIP + objects + temporal hint |

Planner chỉ **đề xuất** modality; nó không tự bật store/model chưa được cấu hình.

Sau khi preview, UI hiển thị checkbox cho từng variant. Bỏ chọn variant không mong muốn trước khi Search; nếu bỏ chọn tất cả, backend fallback về query gốc để không tạo truy vấn rỗng.

## 3. Dò reranker bằng tay

Baseline, không bật Phase 6:

```bash
curl -G -s http://127.0.0.1:8765/api/structured-search \
  --data-urlencode 'q=biển hiệu chữ Samsung' \
  --data-urlencode 'enable_clip=true' \
  --data-urlencode 'enable_ocr=true' \
  --data-urlencode 'enable_query_planner=false' \
  --data-urlencode 'enable_reranker=false' > artifacts/phase6/baseline.json
```

Planner + reranker:

```bash
curl -G -s http://127.0.0.1:8765/api/structured-search \
  --data-urlencode 'q=biển hiệu chữ Samsung' \
  --data-urlencode 'enable_clip=true' \
  --data-urlencode 'enable_ocr=true' \
  --data-urlencode 'enable_query_planner=true' \
  --data-urlencode 'enable_reranker=true' \
  --data-urlencode 'reranker_top_n=20' > artifacts/phase6/reranked.json
```

Dò từng result:

- `pre_rerank_rank`: rank RRF trước rerank.
- `pre_rerank_score`: score trước rerank.
- `rerank_score`/`post_rerank_score`: score mới.
- `rerank_explanation.matched_modalities`.
- `rerank_explanation.requested_modalities`.
- `rerank_explanation.lexical_overlap`.
- `rerank_explanation.contributions`.

Tắt planner/reranker phải tái hiện baseline Phase 5; response không được tự thêm `query_plan` hoặc `reranker`.

## 4. Benchmark before/after

Điền `baseline_results` từ một frozen Phase 5 run và `expected_video_ids` đã chấm tay trong `benchmarks/phase6_queries_v1.json`. Không tune bằng holdout. Seed config được version hóa tại `configs/phase6_reranker_v1.json`.

Tune chỉ trên development:

```bash
python tools/phase6_tune.py \
  --input benchmarks/phase6_queries_v1.json \
  --output-config artifacts/phase6/phase6_reranker_tuned_v1.json
```

Khóa file config trên trước khi chạy holdout.

```bash
python tools/phase6_benchmark.py \
  --input benchmarks/phase6_queries_v1.json \
  --split development --config artifacts/phase6/phase6_reranker_tuned_v1.json \
  --output artifacts/phase6/development.json

python tools/phase6_benchmark.py \
  --input benchmarks/phase6_queries_v1.json \
  --split holdout --config artifacts/phase6/phase6_reranker_tuned_v1.json \
  --output artifacts/phase6/holdout.json
```

Nếu `judged_query_count=0`, MRR phải là `null/unavailable`. Chỉ promote khi holdout Top-1 hoặc MRR tăng, latency đạt yêu cầu và manual review không phát hiện systematic regression.

Chạy UI với config đã khóa:

```bash
python tools/retrieval_ui.py \
  --registry artifacts/registry/data_registry.json \
  --index-dir artifacts/indexes/l21_numpy \
  --phase6-config artifacts/phase6/phase6_reranker_tuned_v1.json \
  --groups L21 --clip-local-files-only
```
