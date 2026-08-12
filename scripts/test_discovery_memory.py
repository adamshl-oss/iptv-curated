#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("discovery_memory.py")
SPEC = importlib.util.spec_from_file_location("discovery_memory_tests", MODULE_PATH)
assert SPEC and SPEC.loader
memory = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = memory
SPEC.loader.exec_module(memory)


class DiscoveryMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = {
            "research_memory": {
                "legacy_baseline_at": "2026-08-07T14:30:00Z",
                "legacy_families": [
                    "official:page",
                    "official:assets",
                    "github:tvg_id",
                    "catalog:*",
                ],
                "families_per_target_per_run": 1,
                "candidate_retry_cooldown_hours": 168,
                "max_run_history": 10,
                "family_cooldown_hours": {
                    "catalog": 24,
                    "official": 72,
                    "official:deep_assets": 168,
                    "github": 168,
                },
            },
            "catalogs": [
                {
                    "name": "fixture-fr",
                    "country": "france",
                    "url": "https://example.test/fr.m3u",
                }
            ],
        }
        self.target = {
            "name": "France 2",
            "tvg_id": "France2.fr",
            "official_url": "https://www.france.tv/france-2/direct.html",
            "aliases": ["France Deux"],
        }
        self.registries = {"france": {"channels": [self.target]}}

    def test_bootstrap_skips_paths_the_legacy_loop_just_repeated(self) -> None:
        history = memory.new_history(
            self.policy, self.registries, "2026-08-07T14:31:00Z"
        )
        planned, _ = memory.plan_searches(
            history,
            self.policy,
            {"france": [self.target]},
            "2026-08-07T14:31:00Z",
        )
        self.assertEqual(len(planned), 1)
        self.assertNotIn(
            planned[0]["family"]["key"],
            {
                "official:page",
                "official:assets",
                "github:tvg_id",
                "catalog:fixture-fr",
            },
        )

    def test_next_wake_advances_to_a_different_family(self) -> None:
        history = memory.new_history(
            self.policy, self.registries, "2026-08-07T14:31:00Z"
        )
        planned, _ = memory.plan_searches(
            history,
            self.policy,
            {"france": [self.target]},
            "2026-08-07T14:31:00Z",
        )
        first = planned[0]
        memory.record_task(
            history,
            self.policy,
            first,
            candidates=[],
            qualified=False,
            now="2026-08-07T14:31:00Z",
        )
        planned_again, _ = memory.plan_searches(
            history,
            self.policy,
            {"france": [self.target]},
            "2026-08-07T14:32:00Z",
        )
        self.assertEqual(len(planned_again), 1)
        self.assertNotEqual(
            first["family"]["key"], planned_again[0]["family"]["key"]
        )

    def test_failed_candidate_is_not_retested_for_one_week(self) -> None:
        history = memory.new_history(
            self.policy, self.registries, "2026-08-07T14:31:00Z"
        )
        planned, _ = memory.plan_searches(
            history,
            self.policy,
            {"france": [self.target]},
            "2026-08-07T14:31:00Z",
        )
        url = "https://cdn.example.test/france2/live.m3u8?token=secret"
        memory.record_task(
            history,
            self.policy,
            planned[0],
            candidates=[
                {"url": url, "source": "fixture", "outcome": "playback_failed"}
            ],
            qualified=False,
            now="2026-08-07T14:31:00Z",
        )
        due, reason = memory.candidate_is_due(
            history, "france", "France 2", url, "2026-08-08T14:31:00Z"
        )
        self.assertFalse(due)
        self.assertIn("cooling down", reason)
        due_later, _ = memory.candidate_is_due(
            history, "france", "France 2", url, "2026-08-14T14:32:00Z"
        )
        self.assertTrue(due_later)
        state = history["targets"]["france::France 2"]["candidates"]
        self.assertNotIn("token=secret", next(iter(state.values()))["url"])

    def test_run_budget_rotates_to_the_oldest_unsearched_channel(self) -> None:
        second = {
            "name": "M6",
            "tvg_id": "M6.fr",
            "official_url": "https://www.m6.fr/m6/direct",
        }
        registries = {"france": {"channels": [self.target, second]}}
        policy = dict(self.policy)
        policy["research_memory"] = dict(self.policy["research_memory"])
        policy["research_memory"]["maximum_tasks_per_run"] = 1
        history = memory.new_history(
            policy, registries, "2026-08-07T14:31:00Z"
        )
        targets = {"france": [self.target, second]}
        first, _ = memory.plan_searches(
            history, policy, targets, "2026-08-07T14:31:00Z"
        )
        memory.record_task(
            history,
            policy,
            first[0],
            candidates=[],
            qualified=False,
            now="2026-08-07T14:31:00Z",
        )
        second_wake, _ = memory.plan_searches(
            history, policy, targets, "2026-08-07T14:32:00Z"
        )
        self.assertNotEqual(first[0]["target"], second_wake[0]["target"])

    def test_wide_sweep_ignores_family_cooldowns_and_expands_target_depth(self) -> None:
        policy = dict(self.policy)
        policy["wide_sweep"] = {
            "families_per_target": 4,
            "maximum_tasks": 60,
        }
        history = memory.new_history(
            policy, self.registries, "2026-08-07T14:31:00Z"
        )
        planned, _ = memory.plan_searches(
            history,
            policy,
            {"france": [self.target]},
            "2026-08-07T14:32:00Z",
            wide=True,
        )
        self.assertEqual(len(planned), 4)
        keys = {task["family"]["key"] for task in planned}
        self.assertEqual(len(keys), 4)

        for task in planned:
            memory.record_task(
                history,
                policy,
                task,
                candidates=[],
                qualified=False,
                now="2026-08-07T14:32:00Z",
            )
        next_planned, _ = memory.plan_searches(
            history,
            policy,
            {"france": [self.target]},
            "2026-08-07T14:33:00Z",
            wide=True,
        )
        next_keys = {task["family"]["key"] for task in next_planned}
        self.assertTrue(keys.isdisjoint(next_keys))


if __name__ == "__main__":
    unittest.main()
