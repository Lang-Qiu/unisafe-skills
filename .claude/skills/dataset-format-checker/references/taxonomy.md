# Unified Harmful-Content Taxonomy

This taxonomy is intentionally broad so that heterogeneous harmful-content datasets can be merged without losing label semantics.

## Categories

| Category | Meaning |
|---|---|
| `hate_discrimination` | Abuse, threats, demeaning content, or exclusion targeting protected or identity-based groups. |
| `harassment_bullying` | Personal abuse, bullying, threats, humiliation, stalking, or intimidation. |
| `sexual_content` | Explicit sexual content, sexual solicitation, or sexualized descriptions. |
| `child_safety` | Any sexual, exploitative, grooming, or endangering content involving minors. |
| `self_harm` | Suicide, self-injury, eating-disorder encouragement, or instructions enabling self-harm. |
| `violence` | Graphic violence, threats, assault, murder, abuse, or instructions to harm people. |
| `weapons` | Weapon construction, acquisition, optimization, concealment, or misuse. |
| `illicit_behavior` | General illegal activity, evasion, theft, vandalism, organized crime, or wrongdoing. |
| `cyber_safety` | Malware, credential theft, unauthorized access, phishing, exploit development, or cyber abuse. |
| `drugs` | Illegal drugs, controlled substances, misuse, production, trafficking, or evasion. |
| `chemical_biological` | Chemical, biological, radiological, or nuclear harmful knowledge and misuse. |
| `fraud_financial_crime` | Scams, impersonation, market abuse, laundering, payment fraud, or financial exploitation. |
| `privacy_pii` | Doxxing, personal data extraction, surveillance, or privacy-invasive requests. |
| `extremism_terrorism` | Terrorist or extremist recruitment, praise, operational assistance, or propaganda. |
| `misinformation` | Deceptive factual manipulation, coordinated disinformation, or harmful false claims. |
| `copyright` | Requests to provide, reproduce, or evade restrictions on protected content. |
| `animal_abuse` | Harm, cruelty, torture, or neglect involving animals. |
| `profanity_toxicity` | General toxicity, profanity, insults, obscene language, or low-level abusive text. |
| `political_persuasion` | Targeted political persuasion or manipulative political influence. |
| `medical_safety` | Unsafe medical advice, diagnosis, dosage, or treatment guidance. |
| `legal_safety` | Unsafe legal advice, evasion, or high-stakes legal guidance. |
| `general_harm` | Harmful content that does not fit a more specific category. |
| `other` | Use only when the original label cannot be mapped reliably. |

## Mapping principles

1. A single source label may map to multiple canonical categories.
2. Keep original labels in `raw_label.original_categories` even after mapping.
3. Use `other` for uncertain mappings rather than inventing a category.
4. Use `canonical_subcategories` for dataset-specific finer labels when useful.
