# Phase 5 - Hướng Dẫn Chạy Và Kiểm Thử

Phase 5 được giữ ở chế độ **opt-in**. Store OCR/ASR không tồn tại thì search mặc định Phase 3/4 vẫn hoạt động; không được diễn giải test fixture thành chất lượng model trên dữ liệu cuộc thi.

## 1. Chuẩn bị môi trường

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-test.txt
```

Không cài PaddleOCR/faster-whisper hoặc tải model trước khi chốt model, GPU và phạm vi pilot.

## 2. Kiểm tra code nhanh

```bash
python -m compileall -q src tools tests
python -m pytest tests/test_phase5_schema.py tests/test_phase5_store.py tests/test_phase5_hybrid.py -q
python -m pytest tests/test_retrieval_ui_static.py tests/test_structured_api.py -q
python -m pytest tests -q
git diff --check
```

`pytest` kiểm tra contract bằng fixture; nó không thay thế OCR/ASR review hoặc benchmark.

## 3. Bước 1 và 8 - audit dữ liệu, video và audio

```bash
python tools/audit_phase5_data.py \
  --data-root data --groups L21 --probe-audio \
  --output artifacts/phase5/audits/l21_data_audio.json
```

Exit code `2` nghĩa là thiếu `data/`; `NO_AUDIO` là trạng thái dữ liệu, không phải lỗi inference.

## 4. Bước 3 - kiểm tra benchmark annotation

Mở `benchmarks/phase5_ocr_asr_queries_v1.json`, thay `expected: []` bằng judgement đã kiểm tra thủ công. Development dùng để tuning; holdout chỉ chạy sau khi khóa cấu hình.

```bash
python -m json.tool benchmarks/phase5_ocr_asr_queries_v1.json >/dev/null
```

## 5. Bước 4 và 9 - pilot có giới hạn

Tool từ chối quá 10 input để tránh vô tình chạy toàn corpus:

```bash
python tools/phase5_pilot.py --modality ocr \
  --inputs data/keyframes/L21_V001/001.jpg data/keyframes/L21_V001/002.jpg \
  --model '<ocr-model-da-duyet>' \
  --output artifacts/phase5/pilots/ocr.json

python tools/phase5_pilot.py --modality asr \
  --inputs data/videos/L21/L21_V001.mp4 \
  --model '<whisper-model-da-duyet>' \
  --output artifacts/phase5/pilots/asr.json
```

Output raw của model cần được chuẩn hóa về JSONL schema `OcrFrame`/`AsrTranscript` và review thủ công trước khi build store.

## 6. Bước 5, 10 và 11 - build/search FTS5

```bash
python tools/build_phase5_store.py \
  --ocr-jsonl artifacts/phase5/raw/ocr_l21.jsonl \
  --asr-jsonl artifacts/phase5/raw/asr_l21.jsonl \
  --index-dir artifacts/indexes/l21_numpy \
  --output artifacts/phase5/stores/phase5_l21.sqlite3 --overwrite

python tools/phase5_search.py --store artifacts/phase5/stores/phase5_l21.sqlite3 \
  --modality ocr --query 'thời sự 19h' --min-confidence 0.5 --top-k 10

python tools/phase5_search.py --store artifacts/phase5/stores/phase5_l21.sqlite3 \
  --modality asr --query 'xin chào quý vị' --top-k 10
```

Kiểm tra raw text, bbox, `start_time/end_time`, `mapping_kind` và `distance_seconds`; không chỉ nhìn rank.

## 7. Bước 6, 12 và 13 - API/UI, timeline và RRF

```bash
python tools/retrieval_ui.py \
  --registry artifacts/registry/data_registry.json \
  --index-dir artifacts/indexes/l21_numpy --groups L21 \
  --phase5-store artifacts/phase5/stores/phase5_l21.sqlite3 \
  --clip-local-files-only

curl -s http://127.0.0.1:8765/api/health
curl -G -s http://127.0.0.1:8765/api/structured-search \
  --data-urlencode 'q=thời sự 19h' \
  --data-urlencode 'enable_clip=false' \
  --data-urlencode 'enable_ocr=true' \
  --data-urlencode 'ocr_min_confidence=0.5'

curl -G -s http://127.0.0.1:8765/api/neighborhood \
  --data-urlencode 'video_id=L21_V001' \
  --data-urlencode 'keyframe_id=1' --data-urlencode 'radius=3'
```

Trong UI phải kiểm tra OCR/ASR chip, text evidence, bbox/raw output bên ngoài UI nếu cần, transcript timeline và seek video. Khi bỏ chọn OCR/ASR, thứ hạng Phase 4 phải giữ nguyên.

## 8. Bước 7 và 14 - benchmark/ablation

```bash
python tools/phase5_benchmark.py \
  --queries benchmarks/phase5_ocr_asr_queries_v1.json \
  --store artifacts/phase5/stores/phase5_l21.sqlite3 \
  --split development --top-k 10 \
  --output artifacts/phase5/benchmarks/development.json

python tools/phase5_benchmark.py \
  --queries benchmarks/phase5_ocr_asr_queries_v1.json \
  --store artifacts/phase5/stores/phase5_l21.sqlite3 \
  --split holdout --top-k 10 \
  --output artifacts/phase5/benchmarks/holdout.json
```

Nếu `judged_query_count=0`, MRR phải là `null/unavailable`; không được báo thành 0 hoặc dùng để promote. Full hybrid ablation phải chạy cấu hình CLIP-only, OCR-only, ASR-only, Phase 4 và Phase 4+OCR+ASR từ cùng frozen query set.

## 9. Tiêu chí promote

Chỉ promote khi có dữ liệu thật, judgement thủ công, holdout không dùng để tune, timestamp seek đúng, regression test pass và latency phù hợp. Nếu thiếu một trong các bằng chứng đó, giữ Phase 5 opt-in.
