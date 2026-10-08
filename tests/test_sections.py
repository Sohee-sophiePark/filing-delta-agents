from filing_delta.sections import blocks, items, note, risk_factors

B = '<div><span style="font-weight:700">{}</span></div>'
P = "<div>{}</div>"

HTML = "".join(
    [
        P.format("Item 1A. Risk Factors 12"),  # table of contents
        P.format("Item 1B. Unresolved Staff Comments 30"),
        B.format("Item 1A. Financial Statements of Parent Inc."),  # combined filing, wrong title
        P.format("Statement table"),
        B.format("ITEM 1A. RISK FACTORS"),
        B.format("Risks Related to Our Business"),  # category heading, no period
        B.format("Fuel prices could rise sharply and hurt our results."),
        P.format("Fuel is a major cost."),
        B.format("Item 1A. Risk Factors"),  # running page header
        P.format("Hedging is limited."),
        B.format("Our debt agreements contain restrictive covenants."),
        P.format("Covenants limit borrowing."),
        B.format("ITEM 1B. UNRESOLVED STAFF COMMENTS"),
        P.format("None."),
        B.format("ITEM 8. FINANCIAL STATEMENTS"),
        B.format("NOTE 5. LEASES"),
        P.format("Lease text."),
        B.format("NOTE 6. DEBT"),
        P.format("Debt text."),
        B.format("10.75% Senior Secured Notes"),
        P.format("Notes text."),
        B.format("NOTE 7. INCOME TAXES"),
        P.format("Tax text."),
    ]
)


def test_items_skip_toc_wrong_title_and_page_headers():
    its = items(blocks(HTML), {"1A": "risk", "8": "financial"})
    texts = [b.text for b in its["1A"]]
    assert texts[0] == "Risks Related to Our Business"
    assert "Item 1A. Risk Factors" not in texts
    assert "Statement table" not in texts
    assert texts[-1] == "Covenants limit borrowing."


def test_risk_factors_drop_category_headings_and_keep_bodies():
    rfs = risk_factors(items(blocks(HTML), {"1A": "risk"})["1A"])
    assert [r.heading for r in rfs] == [
        "Fuel prices could rise sharply and hurt our results.",
        "Our debt agreements contain restrictive covenants.",
    ]
    assert rfs[0].body == "Fuel is a major cost. Hedging is limited."


def test_debt_note_runs_to_next_note():
    item_8 = items(blocks(HTML), {"8": "financial"})["8"]
    assert [b.text for b in note(item_8, r"\bdebt\b")] == [
        "Debt text.",
        "10.75% Senior Secured Notes",
        "Notes text.",
    ]
