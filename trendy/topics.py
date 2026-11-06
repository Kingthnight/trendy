from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Topic:
    name: str
    patterns: tuple[str, ...]
    title_patterns: tuple[str, ...] = ()


def topic(name: str, *patterns: str, title: tuple[str, ...] = ()) -> Topic:
    return Topic(name, patterns, title)


# Phrases are matched after lowercasing and turning hyphens into spaces.
# Broad words that show up in almost every abstract are title-only.
TOPICS: tuple[Topic, ...] = (
    topic(
        "Large language models",
        r"large language models?",
        r"\bllms?\b",
        r"foundation models?",
        r"instruction tun\w+",
        r"\bgpt\b",
        r"\bbert\b",
        title=(r"language models?",),
    ),
    topic(
        "Reasoning",
        r"chain of thought",
        r"test time scaling",
        r"test time compute",
        r"mathematical reasoning",
        r"math reasoning",
        r"reasoning models?",
        r"multi step reasoning",
    ),
    topic(
        "Alignment and safety",
        r"\brlhf\b",
        r"\brlaif\b",
        r"\bdpo\b",
        r"\bgrpo\b",
        r"direct preference opt\w*",
        r"preference optimization",
        r"from human feedback",
        r"reward models?",
        r"jailbreak\w*",
        r"red team\w*",
        r"ai safety",
        r"model alignment",
        r"safety alignment",
        r"preference alignment",
    ),
    topic(
        "Agents",
        r"\bagentic\b",
        r"multi agents?",
        r"language agents?",
        r"tool use",
        r"tool using",
        r"tool calling",
        r"function calling",
        r"ai agents?",
        r"embodied agents?",
        title=(r"\bagents?\b",),
    ),
    topic(
        "Retrieval and RAG",
        r"retrieval augmented",
        r"\brag\b",
        r"dense retrieval",
        r"neural retrieval",
    ),
    topic(
        "Reinforcement learning",
        r"reinforcement learning",
        r"offline rl",
        r"policy gradient",
        r"markov decision",
        r"q learning",
        r"actor critic",
        r"imitation learning",
        r"\bppo\b",
        r"\bdqn\b",
        r"\brl\b",
    ),
    topic(
        "Diffusion and generative models",
        r"\bdiffusion\b",
        r"flow matching",
        r"rectified flow",
        r"score based",
        r"generative adversarial",
        r"\bgans?\b",
        r"text to image",
        r"image generation",
    ),
    topic(
        "Multimodal",
        r"multimodal",
        r"multi modal",
        r"vision language",
        r"text to video",
        r"video generation",
        r"\bvlms?\b",
        r"\bmllms?\b",
    ),
    topic(
        "Graph learning",
        r"graph neural",
        r"\bgnns?\b",
        r"graph transformers?",
        r"graph learning",
        r"knowledge graphs?",
    ),
    topic(
        "Efficiency and compression",
        r"quantiz\w*",
        r"\bpruning\b",
        r"\bdistillation\b",
        r"speculative decoding",
        r"low rank adaptation",
        r"\blora\b",
        r"model compression",
        r"kv cache",
        r"parameter efficient",
    ),
    topic(
        "Mixture of experts",
        r"mixture of experts",
        r"\bmoe\b",
    ),
    topic(
        "Robustness and shift",
        r"\badversarial\b",
        r"out of distribution",
        r"distribution shift",
        r"domain generalization",
        r"domain adaptation",
        r"\bood\b",
        title=(r"\brobustness\b",),
    ),
    topic(
        "Learning theory",
        r"generalization bounds?",
        r"pac bayes",
        r"sample complexity",
        r"learning theory",
        r"\brademacher\b",
        r"vc dimension",
    ),
    topic(
        "Self-supervised learning",
        r"self supervised",
        r"contrastive learning",
        r"masked autoencoder",
    ),
    topic(
        "Time series",
        r"time series",
        r"\bforecasting\b",
        r"temporal forecasting",
    ),
    topic(
        "Causal ML",
        r"causal inference",
        r"causal discovery",
        r"treatment effects?",
        r"causal representation",
    ),
    topic(
        "Privacy and federated learning",
        r"\bfederated\b",
        r"differential privacy",
    ),
    topic(
        "Scientific machine learning",
        r"physics informed",
        r"neural operators?",
        r"scientific machine learning",
        r"\bpinns?\b",
    ),
    topic(
        "Healthcare and life sciences",
        r"\bclinical\b",
        r"medical imag\w*",
        r"electronic health",
        r"drug discovery",
        r"\bbiomarkers?\b",
        r"protein structure",
        r"protein language",
        r"single cell",
        r"histopathology",
        r"\bpatients?\b",
        r"\bhealthcare\b",
        r"drug target",
        r"\bretinal\b",
    ),
    topic(
        "Interpretability",
        r"interpretability",
        r"explainability",
        r"explainable",
        r"mechanistic interpret\w*",
        r"feature attribution",
    ),
    topic(
        "Robotics",
        r"\brobots?\b",
        r"\brobotics?\b",
        r"\brobotic\b",
    ),
    topic(
        "Speech and audio",
        r"speech recognition",
        r"text to speech",
        r"\basr\b",
        r"speech synthesis",
        r"audio generation",
        r"spoken language",
    ),
    topic(
        "Fairness",
        r"\bfairness\b",
        r"algorithmic bias",
        r"demographic parity",
        r"equalized odds",
    ),
    topic(
        "In-context learning and prompting",
        r"in context learning",
        r"prompt tuning",
        r"\bprompting\b",
    ),
    topic(
        "Recommender systems",
        r"recommenders?",
        r"recommendation systems?",
        r"recommendation models?",
        r"sequential recommendation",
    ),
    topic(
        "World models",
        r"world models?",
    ),
    topic(
        "Continual learning",
        r"continual learning",
        r"lifelong learning",
        r"catastrophic forgetting",
        r"incremental learning",
    ),
    topic(
        "Uncertainty",
        r"uncertainty quantification",
        r"conformal prediction",
        r"epistemic uncertainty",
        r"\bcalibration\b",
    ),
    topic(
        "Optimization",
        r"learning rate schedul\w*",
        r"sharpness aware",
        r"bilevel optim\w*",
        r"stochastic gradient",
        r"\badamw\b",
    ),
    topic(
        "Computer vision",
        r"object detection",
        r"semantic segmentation",
        r"instance segmentation",
        r"pose estimation",
        r"image classification",
        r"visual recognition",
        r"gaussian splatting",
        title=(r"\bsegmentation\b",),
    ),
    topic(
        "Data-centric ML",
        r"synthetic data",
        r"data curation",
        r"data selection",
        r"dataset distillation",
        r"data filtering",
        r"training data attribution",
    ),
    topic(
        "Unlearning",
        r"machine unlearning",
        r"\bunlearning\b",
    ),
    topic(
        "Scaling",
        r"scaling laws?",
    ),
    topic(
        "Long context",
        r"long context",
        r"context windows?",
        r"extended context",
    ),
    topic(
        "State space models",
        r"state space models?",
        r"\bmamba\b",
    ),
    topic(
        "Code models",
        r"code generation",
        r"program synthesis",
        r"code language models?",
    ),
    topic(
        "Factuality",
        r"hallucinat\w*",
        r"\bfactuality\b",
    ),
    topic(
        "Few-shot and meta-learning",
        r"meta learning",
        r"few shot",
        r"one shot learning",
    ),
    topic(
        "Active learning",
        r"active learning",
    ),
    topic(
        "Anomaly detection",
        r"anomaly detection",
        r"outlier detection",
    ),
    topic(
        "Transfer learning",
        title=(r"transfer learning",),
    ),
    topic(
        "Evaluation",
        title=(r"\bbenchmarks?\b", r"\bleaderboards?\b"),
    ),
)


def _compile(patterns: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)


_COMPILED = tuple(
    (item.name, _compile(item.patterns), _compile(item.title_patterns)) for item in TOPICS
)


def topic_names() -> tuple[str, ...]:
    return tuple(item.name for item in TOPICS)


def _norm(text: str) -> str:
    text = text.lower().replace("–", " ").replace("—", " ")
    text = re.sub(r"[-_/]+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def match_topics(title: str, abstract: str) -> frozenset[str]:
    """Return theme names found in the text. The text itself is not retained."""
    title_text = _norm(title)
    blob = f"{title_text} {_norm(abstract)}".strip()
    found: list[str] = []
    for name, body_patterns, title_patterns in _COMPILED:
        if any(pattern.search(blob) for pattern in body_patterns) or any(
            pattern.search(title_text) for pattern in title_patterns
        ):
            found.append(name)
    return frozenset(found)
