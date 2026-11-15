"""Corpus filtering and generation guards."""

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from model import FORBIDDEN_WORDS, SimpleLLM, load_corpus


class ModelBehaviorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = SimpleLLM(max_context=7)
        cls.model.train(load_corpus())

    def test_german_article_stays_in_the_dialogue(self):
        self.assertIn("die", self.model.vocab)
        self.assertIn(("ja", "die"), self.model.transitions)
        self.assertNotIn("hate", self.model.vocab)
        for word in FORBIDDEN_WORDS:
            self.assertNotIn(word, self.model.vocab)

    def test_unknown_and_blank_prompts_still_respond(self):
        random.seed(0)
        unknown = self.model.generate("zzzznotaword", max_tokens=8)
        self.assertTrue(unknown)
        self.assertIn("Bitte", self.model.generate("   "))

    def test_runtime_filter_skips_blocked_words(self):
        model = SimpleLLM(max_context=2)
        model.train("hello there friend")
        model.transitions[("hello",)] = {"hate": 100, "friend": 1}
        random.seed(0)
        for _ in range(10):
            text = model.generate("hello", max_tokens=1, temperature=0.1)
            self.assertNotIn("hate", text.split())

        model.transitions[("hello",)] = {"hate": 5}
        self.assertNotIn("hate", model.generate("hello", max_tokens=5).split())


if __name__ == "__main__":
    unittest.main()
