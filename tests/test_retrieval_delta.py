from filing_delta.corpus import Passage, passages
from filing_delta.delta import align, word_diff
from filing_delta.retrieval import BM25


def P(i, text, ticker="DAL", current=True):
    return Passage(i, ticker, "10-K", "2026-02-11", "2025-12-31", "7", text, "u", current)


def test_bm25_ranks_relevant_first_and_expands_analyst_wording():
    bm = BM25(
        [
            P("a", "Fuel expense decreased on lower jet fuel prices."),
            P("b", "No borrowings were outstanding under the revolving credit facility."),
            P("c", "The revolving credit facility was undrawn at year end.", ticker="UAL"),
            P("d", "Prior year revolving credit facility text.", current=False),
        ]
    )
    hits = bm.search("Has the airline drawn on its revolver?", k=3, ticker="DAL", current=True)
    assert [p.id for p, _ in hits] == ["b"]


def test_passages_merge_short_paragraphs_and_keep_first_id():
    doc = {
        "form": "10-K",
        "filed": "f",
        "period": "p",
        "url": "u",
        "sections": {"7": [{"id": f"x#7-{i}", "text": "word " * 30} for i in range(6)]},
    }
    ps = passages(doc, "DAL")
    assert [p.id for p in ps] == ["x#7-0", "x#7-3"]
    assert all(p.current for p in ps)


def rf(h, body):
    return {"id": h, "heading": h, "body": body}


def test_align_labels_each_kind_of_change():
    prior = [
        rf("Fuel prices may rise.", "Fuel is our largest cost in 2024."),
        rf("Our debt has covenants.", "Covenants limit borrowing and require minimum liquidity."),
        rf("Pension obligations are large.", "We fund pensions."),
        rf("Labor disputes may occur.", "Unions represent most employees."),
    ]
    current = [
        rf("Fuel prices may rise.", "Fuel is our largest cost in 2025."),
        rf(
            "Our debt has covenants.",
            "Covenants now also require collateral coverage tests each quarter.",
        ),
        rf("Government shutdowns may hurt us.", "Air traffic control could slow."),
        rf("Labor disputes may occur.", "Unions represent most employees."),
    ]
    got = {(c.current or c.prior)["heading"]: c.status for c in align(prior, current)}
    assert got == {
        "Fuel prices may rise.": "modified",  # 1 of 7 words changed: above the 5% cut
        "Our debt has covenants.": "modified",
        "Government shutdowns may hurt us.": "added",
        "Pension obligations are large.": "removed",
        "Labor disputes may occur.": "unchanged",
    }


def test_word_diff_marks_inserted_and_deleted_words():
    assert word_diff("cost in 2024", "cost in 2025") == [
        ("equal", "cost in"),
        ("delete", "2024"),
        ("insert", "2025"),
    ]
