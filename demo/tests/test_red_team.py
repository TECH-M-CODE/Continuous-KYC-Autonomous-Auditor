"""Red-team safety: the drill-isolation invariant is the one that must never
regress. A drill that leaks a real alert mid-demo is a disaster."""

import pytest
from demo.red_team import (
    assert_drill_isolation, run_drill, EvasionVariant, VariantClass, DrillReport,
)


class FakeInject:
    def __init__(self):
        self.n = 0
    async def inject(self, **kw):
        assert kw["is_drill"] is True   # every red-team injection MUST be a drill
        self.n += 1
        return f"drill-{self.n}"


class CleanProbe:
    async def was_screened_hit(self, *, event_id): return True
    async def real_alert_exists(self, *, event_id): return False
    async def real_sar_exists(self, *, event_id): return False


class LeakyProbe(CleanProbe):
    async def real_alert_exists(self, *, event_id): return True


class FakeGateway:
    def __init__(self, variants):
        self._variants = variants
    async def complete(self, prompt, *, schema, task_tag):
        class R: ...
        r = R()
        r.variants = self._variants
        return r


class V:  # mimics a schema row
    def __init__(self, original, variant, variant_class):
        self.original, self.variant, self.variant_class = original, variant, variant_class


@pytest.mark.asyncio
async def test_isolation_passes_when_clean():
    await assert_drill_isolation(FakeInject(), CleanProbe())  # no raise


@pytest.mark.asyncio
async def test_isolation_aborts_on_leak():
    with pytest.raises(RuntimeError, match="ISOLATION BREACH"):
        await assert_drill_isolation(FakeInject(), LeakyProbe())


@pytest.mark.asyncio
async def test_run_drill_produces_report():
    gw = FakeGateway([
        V("Acme", "Akme", "typo_squat"),
        V("Acme", "Ａcme", "transliteration"),
        V("Acme", "Acme Trading Nominees", "shell_name"),
    ])
    report = await run_drill(gateway=gw, inject=FakeInject(), probe=CleanProbe(),
                             seed_names=["Acme"], variant_schema=object)
    assert isinstance(report, DrillReport)
    assert report.total == 3
    assert report.isolation_verified
    assert "/3 evasion variants caught" in report.headline


@pytest.mark.asyncio
async def test_run_drill_aborts_before_injection_if_isolation_breached():
    gw = FakeGateway([V("Acme", "Akme", "typo_squat")])
    with pytest.raises(RuntimeError, match="ISOLATION BREACH"):
        await run_drill(gateway=gw, inject=FakeInject(), probe=LeakyProbe(),
                        seed_names=["Acme"], variant_schema=object)