import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server
VAT='{"periodKey":"24A1","vatDueSales":1000,"totalVatDue":1200,"currency":"GBP"}'
def test_parse():
    p=server.parse_tax(VAT); assert p.tax_kind=="VAT"; assert p.period=="24A1"; assert p.total=="1200"
def test_govern():
    g=server.govern_tax(VAT); assert any("MTD" in f for f in g.frameworks)
def test_validate():
    assert server.validate_tax(VAT).valid
