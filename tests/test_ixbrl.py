from filing_delta.ixbrl import facts

HTML = """
<html><body>
<ix:header><ix:resources>
<xbrli:context id="fy"><xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate>
<xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
<xbrli:context id="ye"><xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period>
</xbrli:context>
<xbrli:context id="ye-ent"><xbrli:entity><xbrli:segment>
<xbrldi:explicitMember dimension="dei:LegalEntityAxis">x:ParentMember</xbrldi:explicitMember>
</xbrli:segment></xbrli:entity><xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period></xbrli:context>
</ix:resources></ix:header>
<p>Operating income <ix:nonFraction name="us-gaap:OperatingIncomeLoss" contextRef="fy" unitRef="usd"
 scale="6" format="ixt:num-dot-decimal" id="f1"><span>5,822</span></ix:nonFraction></p>
<p>Interest, net <ix:nonFraction name="us-gaap:InterestIncomeExpenseNonoperatingNet" contextRef="fy"
 unitRef="usd" scale="6" sign="-" id="f2">679</ix:nonFraction></p>
<p>Investments <ix:nonFraction name="us-gaap:ShortTermInvestments" contextRef="ye" unitRef="usd"
 scale="6" format="ixt:fixed-zero" id="f3">—</ix:nonFraction></p>
<p>Debt <ix:nonFraction name="us-gaap:LongTermDebt" contextRef="ye-ent" unitRef="usd" scale="6"
 format="ixt:num-dot-decimal" id="f4">21,383</ix:nonFraction></p>
<p>Count <ix:nonFraction name="x:Words" contextRef="ye" unitRef="pure" format="ixt-sec:numwordsen"
 id="f5">three</ix:nonFraction></p>
</body></html>
"""


def test_values_periods_and_dimensions():
    by_id = {f.fact_id: f for f in facts(HTML)}
    assert by_id["f1"].value == 5_822_000_000
    assert (by_id["f1"].start, by_id["f1"].end) == ("2025-01-01", "2025-12-31")
    assert by_id["f2"].value == -679_000_000
    assert by_id["f3"].value == 0 and by_id["f3"].start is None
    assert by_id["f4"].dims == (("dei:LegalEntityAxis", "x:ParentMember"),)
    assert by_id["f1"].dims == ()


def test_non_numeric_formats_are_skipped():
    assert "f5" not in {f.fact_id for f in facts(HTML)}
