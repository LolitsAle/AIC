from __future__ import annotations

import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from aic_retrieval.phase5_schema import AsrSegment,AsrTranscript,OcrDetection,OcrFrame
from aic_retrieval.phase5_store import create_store,ingest_asr,ingest_ocr
from aic_retrieval.search import load_numpy_index


def main()->int:
    parser=argparse.ArgumentParser(description="Build the local SQLite FTS5 OCR/ASR evidence store.")
    parser.add_argument("--ocr-jsonl",type=Path); parser.add_argument("--asr-jsonl",type=Path); parser.add_argument("--index-dir",type=Path,required=True); parser.add_argument("--output",type=Path,required=True); parser.add_argument("--overwrite",action="store_true")
    args=parser.parse_args()
    if args.output.exists() and not args.overwrite: raise FileExistsError(f"store already exists: {args.output}; pass --overwrite to rebuild")
    if args.overwrite: args.output.unlink(missing_ok=True)
    _,refs,_=load_numpy_index(args.index_dir); connection=create_store(args.output); ocr_count=asr_count=0
    if args.ocr_jsonl: ocr_count=ingest_ocr(connection,load_ocr(args.ocr_jsonl))
    if args.asr_jsonl: asr_count=ingest_asr(connection,load_asr(args.asr_jsonl),refs)
    connection.close(); print(json.dumps({"ocr_detections":ocr_count,"asr_segments":asr_count,"output":str(args.output)})); return 0


def rows(path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip(): yield json.loads(line)


def load_ocr(path):
    for raw in rows(path):
        yield OcrFrame(raw["video_id"],int(raw["keyframe_id"]),int(raw["frame_idx"]),float(raw["pts_time"]),float(raw["fps"]),tuple(OcrDetection(item["text"],float(item["confidence"]),tuple(tuple(point) for point in item["bbox"])) for item in raw.get("detections",[])),run_id=raw.get("run_id","unknown"))


def load_asr(path):
    for raw in rows(path):
        yield AsrTranscript(raw["video_id"],raw["status"],tuple(AsrSegment(int(item["segment_id"]),float(item["start_time"]),float(item["end_time"]),item["text"],item.get("confidence")) for item in raw.get("segments",[])),raw.get("language"),raw.get("duration"),run_id=raw.get("run_id","unknown"))


if __name__=="__main__": raise SystemExit(main())
