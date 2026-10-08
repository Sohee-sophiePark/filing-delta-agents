from filing_delta.ingest import cross_check, metrics, select


def sub(rows):
    keys = ["form", "filingDate", "reportDate", "accessionNumber", "primaryDocument", "items"]
    return {"filings": {"recent": {k: [r[i] for r in rows] for i, k in enumerate(keys)}}}


def test_select_latest_annuals_and_filings_since():
    s = sub(
        [
            ("8-K", "2026-03-01", "", "a8", "d", "2.03"),
            ("10-K", "2026-02-10", "2025-12-31", "k3", "d", ""),
            ("10-Q", "2026-05-01", "2026-03-31", "q1", "d", ""),
            ("8-K", "2025-06-01", "", "old8", "d", "7.01"),
            ("10-K", "2025-02-10", "2024-12-31", "k2", "d", ""),
            ("10-K", "2024-02-10", "2023-12-31", "k1", "d", ""),
            ("10-K", "2023-02-10", "2022-12-31", "k0", "d", ""),
        ]
    )
    got = [x["accession"] for x in select(s, 3)]
    assert got == ["k3", "k2", "k1", "q1", "a8"]


def fact(concept, value, end, start=None, dims=(), fid="f"):
    return {
        "concept": concept,
        "value": value,
        "start": start,
        "end": end,
        "dims": dims,
        "fact_id": fid,
    }


CFG = {
    "metrics": {
        "interest": {
            "label": "Interest expense",
            "period": "duration",
            "concepts": ["InterestExpenseNonoperating"],
        },
        "debt": {"label": "Total debt", "period": "instant", "concepts": ["LongTermDebt"]},
    },
    "overrides": {
        "XYZ": {
            "interest": {
                "label": "Interest expense, net",
                "concepts": ["InterestIncomeExpenseNonoperatingNet"],
                "negate": True,
            },
            "debt": {"dims": {"dei:LegalEntityAxis": "x:ParentMember"}},
        }
    },
}
TENKS = [
    {
        "accession": "k2",
        "filed": "2026-02-10",
        "period": "2025-12-31",
        "facts": [
            fact(
                "us-gaap:InterestIncomeExpenseNonoperatingNet",
                -679e6,
                "2025-12-31",
                "2025-01-01",
                fid="i25",
            ),
            fact("us-gaap:LongTermDebt", 9e9, "2025-12-31", fid="noise"),  # wrong dims for XYZ
            fact(
                "us-gaap:LongTermDebt",
                13e9,
                "2025-12-31",
                dims=(("dei:LegalEntityAxis", "x:ParentMember"),),
                fid="d25",
            ),
        ],
    },
    {"accession": "k1", "filed": "2025-02-10", "period": "2024-12-31", "facts": []},
]


def test_metrics_apply_overrides_dims_negate_and_mark_missing():
    m = metrics(CFG, "XYZ", TENKS)
    assert m["interest"]["label"] == "Interest expense, net"
    assert m["interest"]["values"][2025]["value"] == 679e6
    assert m["debt"]["values"][2025]["fact_id"] == "d25"
    assert m["debt"]["values"][2024] is None


def test_cross_check_counts_and_flags_mismatch():
    index = {
        "metrics": {
            "debt": {
                "values": {
                    2025: {"value": 13e9, "concept": "us-gaap:LongTermDebt", "accession": "k2"}
                }
            }
        }
    }
    api = {
        "facts": {
            "us-gaap": {
                "LongTermDebt": {
                    "units": {"USD": [{"accn": "k2", "end": "2025-12-31", "val": 12e9}]}
                }
            }
        }
    }
    compared, issues = cross_check(index, api)
    assert compared == 1 and len(issues) == 1
