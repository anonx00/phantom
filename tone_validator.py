"""
Dynamic tone validation system for tweet content.
Uses pattern categories and regex for flexible, maintainable validation.
"""
import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ToneValidator:
    """
    Validates tweet tone to avoid robotic, formal, preachy, or forced casual language.
    Uses categorized regex patterns for maintainable, dynamic validation.
    """

    def __init__(self):
        # Observational/preachy phrases - sound like watching from outside
        self.observational_patterns = [
            r'\b(good|great|nice|glad|happy) to see\b',
            r'\b(good|great|nice) to hear\b',
            r'\bit\'s (good|great|nice) that\b',
        ]

        # Meta-commentary - talking about the content instead of stating it
        self.meta_commentary_patterns = [
            r'\b(wild|crazy|interesting|fascinating) to think about\b',
            r'\bmakes (you|me) think\b',
            r'\bmakes (sense|you wonder)\b',
            r'\bworth (thinking|noting|mentioning)\b',
        ]

        # Filler words/phrases at start
        self.filler_start_patterns = [
            r'^So,?\s',
            r'^Well,?\s',
            r'^Look,?\s',
            r'^Okay,?\s',
        ]

        # Filler words/phrases at end
        self.filler_end_patterns = [
            r',?\s*(honestly|frankly|really|literally)[\.\!]$',
            r',?\s*finally[\.\!]$',
            r',?\s*to be honest[\.\!]$',
            r',?\s*if (you ask me|i\'m being honest)[\.\!]$',
        ]

        # Formal/robotic questions
        self.formal_question_patterns = [
            r'\b(how|what) (will|does|can) (this|that) (impact|mean|affect)\b',
            r'\b(what|how) (does|will) this mean for\b',
            r'\bare .+ (obsolete|dead|finished)\?',
        ]

        # Hedging/uncertainty - sounds indecisive
        self.hedging_patterns = [
            r'\b(starting|beginning) to\b',
            r'\b(seems|appears) (like|to be)\b',
            r'\b(might|could|may) be (a|the)\b',
            r'\b(feels|sounds) like\b',
        ]

        # Forced casual - trying too hard to sound casual
        self.forced_casual_patterns = [
            r'\bgotta\s',
            r'\bwanna\s',
            r'\bgonna\s',
            r'\bkinda\s',
            r'\bsorta\s',
        ]

        # Awkward phrasing
        self.awkward_patterns = [
            r'\bpopping up\b',
            r'\bin the wild\b',
            r'\bout there\b',
            r'\bthese days\b',
        ]

        # Overhype/marketing speak
        self.marketing_patterns = [
            r'\b(revolutionary|groundbreaking|game-?changer)\b',
            r'\b(unleash|unlock|transform)\b',
            r'\b(amazing|incredible|unbelievable)\b',
            r'\bthe future of\b',
        ]

        # US-centric language (bot is Australian, global perspective)
        self.us_centric_patterns = [
            r'\bhome soil\b',
            r'\bcame home\b',
            r'\bcoming home\b',
            r'\bback home\b',
            r'\bdomestic (tech|production)\b',
            r'\bstateside\b',
            r'\bat home\b.*\b(here|US|USA|America)\b',
        ]

        # Corporate speak
        self.corporate_patterns = [
            r'\b(excited|pleased|happy) to (announce|share)\b',
            r'\bcheck (out|this out)\b',
            r'\bread more\b',
            r'\blearn more\b',
            r'\bin an effort to\b',
            r'\blooking forward to\b',
        ]

    def validate(self, content: str) -> Tuple[bool, Optional[str]]:
        """
        Validates content tone.
        Returns (is_valid, reason_if_invalid)
        """
        content_lower = content.lower()

        # Check for style labels leaking
        if content.startswith("Style") or "**Style" in content or "Style A:" in content or "Style B:" in content:
            return False, "Style label leaked into content. Write tweet directly."

        # Check each pattern category
        checks = [
            (self.observational_patterns, "observational/preachy",
             "Sounds preachy. State facts directly, don't observe from outside."),
            (self.meta_commentary_patterns, "meta-commentary",
             "Don't comment on the content. State it directly."),
            (self.filler_start_patterns, "filler start",
             "Don't start with filler words. Jump to the point."),
            (self.filler_end_patterns, "filler ending",
             "Don't end with filler words. End with the fact or short reaction."),
            (self.formal_question_patterns, "formal question",
             "No formal questions. Make statements or rhetorical observations."),
            (self.hedging_patterns, "hedging/uncertain",
             "Sounds uncertain. State facts confidently."),
            (self.forced_casual_patterns, "forced casual",
             "Don't force casual slang. Be naturally conversational."),
            (self.awkward_patterns, "awkward phrasing",
             "Awkward phrasing. Use direct, natural language."),
            (self.marketing_patterns, "marketing/hype",
             "No marketing speak or overhype. State facts plainly."),
            (self.us_centric_patterns, "US-centric",
             "Use global perspective. Bot is Australian, not American."),
            (self.corporate_patterns, "corporate speak",
             "No corporate language. Sound like a person, not a company."),
        ]

        for patterns, category, reason in checks:
            for pattern in patterns:
                if re.search(pattern, content_lower, re.IGNORECASE):
                    match = re.search(pattern, content_lower, re.IGNORECASE)
                    matched_text = match.group() if match else ""
                    logger.warning(f"Tone validation REJECT [{category}]: '{matched_text}' in: {content}")
                    return False, f"{reason} (matched: '{matched_text}')"

        return True, None

    def get_bad_examples(self) -> List[str]:
        """Returns examples of bad tweets for prompts."""
        return [
            'X "Good to see them focusing on real-world risks" (PREACHY)',
            'X "Good to see some verification popping up" (PREACHY + AWKWARD)',
            'X "This is pretty wild to think about" (META-COMMENTARY)',
            'X "Makes sense – gotta test this stuff" (META-COMMENTARY + FORCED CASUAL)',
            'X "So, evals are the next big thing" (FILLER START)',
            'X "Starting to help scientists work faster" (HEDGING)',
            'X "Big deal for anyone working with visuals, honestly." (FILLER END)',
            'X "OpenAI testing AI safety externally. Finally." (FILLER END)',
            'X "How will this impact domestic tech production?" (FORMAL QUESTION)',
            'X "Feels like a big step towards..." (HEDGING + WORDY)',
            'X "Good to see tech getting built on home soil" (PREACHY + US-CENTRIC)',
            'X "This could revolutionize everything!" (MARKETING/OVERHYPE)',
        ]

    def get_good_examples(self) -> List[str]:
        """Returns examples of good tweets for prompts."""
        return [
            '✓ "OpenAI testing AI safety with external experts. About time."',
            '✓ "Gemini detects AI-edited images. Verification matters."',
            '✓ "GPT-5 cuts hallucinations by 40%. Progress."',
            '✓ "Rust adoption up 67% at Fortune 500. Memory safety wins."',
            '✓ "OpenAI and Foxconn building AI factories in the US. America stepping up."',
            '✓ "Evals becoming standard for AI in business. Testing matters."',
        ]
