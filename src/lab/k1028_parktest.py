"""🧭 Q10/28-1 적용 점검 — 고친 src/port.py · src/conc_port.py 사본(k1028_port_new·k1028_conc_new)을 돌려
   추세 칸 주차가 제대로 들어가나 확인. 실제 market/port.json·conc.json 은 건드리지 않음(출력 경로를 market/lab 로 바꿈)
→ market/lab/k1028_parktest.json
"""
import importlib.util, json, shutil, sys, datetime as dt
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
L = ROOT / "market" / "lab"


def load(name, f):
    sp = importlib.util.spec_from_file_location(name, ROOT / "src" / "lab" / f)
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m


port = load("port_new", "k1028_port_new.py")
shutil.copy(ROOT / "market/port_log.json", L / "_k1028_port_log.json")
port.ROOT = ROOT; port.LEDGER = ROOT / "ledger" / "ledger.json"; port.LOG = L / "_k1028_port_log.json"; port.OUT = L / "_k1028_port.json"
port.main()
conc = load("conc_new", "k1028_conc_new.py")
conc.ROOT = ROOT; conc.M = ROOT / "market"; conc.OUT = L / "_k1028_conc.json"
conc.main()
old_p = json.loads((ROOT / "market/port.json").read_text(encoding="utf-8"))
old_c = json.loads((ROOT / "market/conc.json").read_text(encoding="utf-8"))
P = json.loads(port.OUT.read_text(encoding="utf-8"))
C = json.loads(conc.OUT.read_text(encoding="utf-8"))
out = {"at": dt.datetime.now().isoformat(),
       "port": {"asof": P.get("asof"), "trend_park": P.get("trend_park"), "hold": [{k: h.get(k) for k in ("name", "pct", "pct_base", "contrib", "instruments", "us")} for h in P["hold"]],
                "sum_pct": round(sum(h["pct"] for h in P["hold"]), 2), "stat": P.get("stat"), "old_stat": old_p.get("stat"),
                "nav_tail": P["nav"][-5:], "old_nav_tail": old_p["nav"][-5:], "honest": P["honest"]["base"], "old_honest": old_p["honest"]["base"],
                "vol_note": P["vol_rule"]["note"], "kick_vol_note": P["rule"]["vol_rule"]["note"], "changes": P["changes"][:3]},
       "conc": {"now": C.get("now"), "trend_park": C.get("trend_park"), "nav_tail": C["nav"][-5:], "old_nav_tail": old_c["nav"][-5:],
                "events": C["events"][:3], "rule_vol": C["rule"]["vol"]}}
(L / "k1028_parktest.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
for f in ("_k1028_port_log.json", "_k1028_port.json", "_k1028_conc.json"):
    (L / f).unlink(missing_ok=True)
print(json.dumps(out, ensure_ascii=False)[:4000])
