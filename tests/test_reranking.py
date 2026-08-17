import pytest

from aic_retrieval.query_planner import RuleBasedQueryPlanner
from aic_retrieval.reranking import RerankerConfig,rerank_video_results


def result(rank,video,score,ranks,evidence_text=""):
    return {"rank":rank,"video_id":video,"fusion_score":score,"modality_ranks":ranks,"frames":[{"evidence":{"ocr":[{"matched_text":evidence_text}] if evidence_text else [],"asr":[],"metadata":None}}]}


def test_reranker_promotes_aligned_evidence_and_logs_contributions():
    plan=RuleBasedQueryPlanner().plan('biển hiệu chữ "Samsung"')
    results=[result(1,"V1",1.0,{"clip":1,"ocr":None}),result(2,"V2",.99,{"clip":2,"ocr":1},"Samsung")]
    reranked=rerank_video_results(results,plan,RerankerConfig(top_n=2))
    assert [x["video_id"] for x in reranked]==["V2","V1"]
    assert reranked[0]["pre_rerank_rank"]==2 and reranked[0]["rank"]==1
    assert reranked[0]["video_score"]==reranked[0]["post_rerank_score"]
    assert set(reranked[0]["rerank_explanation"]["contributions"]) == {"normalized_original","modality_match","lexical_evidence","planner_alignment"}


def test_reranker_only_reorders_top_n_and_is_deterministic():
    plan=RuleBasedQueryPlanner().plan("person")
    results=[result(i,f"V{i}",1/i,{"clip":i}) for i in range(1,5)]
    reranked=rerank_video_results(results,plan,RerankerConfig(top_n=2))
    assert [x["video_id"] for x in reranked[2:]]==["V3","V4"]
    assert reranked==rerank_video_results(results,plan,RerankerConfig(top_n=2))


def test_reranker_config_rejects_unbounded_or_negative_settings():
    with pytest.raises(ValueError): RerankerConfig(top_n=101)
    with pytest.raises(ValueError): RerankerConfig(modality_match_weight=-1)
