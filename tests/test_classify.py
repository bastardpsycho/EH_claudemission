from fallout.classify import classify


def test_pubmed_types_win():
    c = classify("Something", pubmed_types=["Journal Article", "Practice Guideline"])
    assert (c.label, c.confidence) == ("guideline", "high")
    assert classify("x", pubmed_types=["Meta-Analysis"]).label == "meta_analysis"
    assert classify("x", pubmed_types=["Systematic Review"]).label == "systematic_review"


def test_title_patterns():
    assert classify("Statins and stroke: a meta-analysis").label == "meta_analysis"
    assert classify("A network meta analysis of antidepressants").label == "meta_analysis"
    assert classify("Probiotics: a systematic review").label == "systematic_review"
    assert classify("Clinical practice guidelines for sepsis").label == "guideline"
    assert classify("Guidelines for the management of asthma").label == "guideline"


def test_conservative_negatives():
    assert classify("Adherence to clinical practice guidelines in rural clinics").label == "other"
    assert classify("Probiotics: a narrative review", "review").label == "other"
    assert classify("A randomised controlled trial of X").label == "other"
    assert classify(None).label == "other"
