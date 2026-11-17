# go2_guard.py — 99-27: 보상 지킴 — rsl_rl PPO 가 한 걸음의 보상을 받을 때 무한대 · NaN 을 0 으로, 지나치게 큰 값을 ±LIM 으로 자름.
#   왜 (99-26): 99U5b 의 3164번째에 returns 에 무한대가 들어가 (물리가 한 판에서 터진 것으로 짐작) 학습이 무너지고 대칭이 깨진 채 굳었다.
#   NaN 감시 (ppo.py · 2026-09 고침) 는 그 갱신을 버렸지만, 그 직후의 큰 (유한) 값들로 한 번 크게 잘못 갱신됐다.
#   한 걸음의 보상은 보통 ±0.1 안팎 (dt 0.02 를 곱한 값) — LIM = 10 은 그 100배라 보통의 학습에는 손대지 않는다.
#   일이 생길 때마다 "[보상 지킴] …" 줄을 찍음 (처음 20번 · 그 뒤 100번마다). flat_env_cfg.py 의 REW_GUARD 가 켜졌을 때만 · 그 학습 과정 안에서만.
import torch

LIM = 10.0
_N = {"bad": 0, "big": 0, "calls": 0, "said": 0}


def install():
    import rsl_rl.algorithms.ppo as _ppo
    if getattr(_ppo, "_robotdog_guard99", False):
        return
    _orig = _ppo.PPO.process_env_step

    def _guarded(self, obs, rewards, dones, extras):
        _N["calls"] += 1
        bad = ~torch.isfinite(rewards)
        nb = int(bad.sum())
        if nb:
            rewards = torch.where(bad, torch.zeros_like(rewards), rewards)
        big = rewards.abs() > LIM
        ng = int(big.sum())
        if ng:
            rewards = rewards.clamp(-LIM, LIM)
        if nb or ng:
            _N["bad"] += nb
            _N["big"] += ng
            _N["said"] += 1
            if _N["said"] <= 20 or _N["said"] % 100 == 0:
                print(f"[보상 지킴] 걸음 {_N['calls']} (약 {_N['calls'] // 24}번째) · 무한대 · NaN {nb} 개 → 0 · ±{LIM:g} 넘는 값 {ng} 개 → 자름"
                      f" · 지금까지 {_N['bad']} · {_N['big']} (README 99-27)", flush=True)
        return _orig(self, obs, rewards, dones, extras)

    _ppo.PPO.process_env_step = _guarded
    _ppo._robotdog_guard99 = True
    print(f"[보상 지킴] 켬 — 한 걸음의 보상에서 무한대 · NaN → 0 · ±{LIM:g} 넘으면 자름 (README 99-27)", flush=True)
