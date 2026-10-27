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


def test_cochrane_review_versions():
    c = classify("Colloid solutions for fluid resuscitation", "article", doi="10.1002/14651858.cd001319.pub5")
    assert (c.label, c.confidence) == ("systematic_review", "medium")
    assert classify("x", doi="10.1002/14651858.CD012345.pub12").label == "systematic_review"
    # The bare DOI is usually the protocol, and .pub1 does not occur for reviews.
    assert classify("x", doi="10.1002/14651858.cd012345").label == "other"
    assert classify("x", doi="10.1002/14651858.cd012345.pub1").label == "other"
    assert classify("x", doi="10.1000/journal.pub2").label == "other"
    # Titles and PubMed types still take precedence.
    assert classify("A meta-analysis", doi="10.1002/14651858.cd1.pub2").label == "meta_analysis"
    assert classify("x", pubmed_types=["Meta-Analysis"], doi="10.1002/14651858.cd1.pub2").label == "meta_analysis"
