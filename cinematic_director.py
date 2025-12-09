"""
Cinematic Director - AI-Powered Video Prompt Generator

Gives AI FULL creative control to decide:
- Visual style (cyberpunk, hyperrealistic, abstract, etc.)
- Camera movements and techniques
- Lighting and color grading
- Mood and atmosphere
- Technical specs

Optimized for Vertex AI Veo video generation.
Production-ready with extensive vocabulary for cinematic excellence.
"""

import logging
import random
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class CinematicDirector:
    """
    Production-grade cinematic director for AI video generation.
    Provides rich vocabulary and lets AI make all creative decisions.
    """

    # ============================================================================
    # VISUAL STYLES - Comprehensive aesthetic vocabulary
    # ============================================================================

    VISUAL_STYLES = {
        "cyberpunk": {
            "description": "Neon-soaked dystopian future with high-tech low-life aesthetics",
            "keywords": [
                "cyberpunk", "neon lights", "holographic displays", "rain-soaked streets",
                "blade runner aesthetic", "dystopian cityscape", "chrome and glass",
                "purple and cyan neon", "dark alleys", "urban decay", "tech noir"
            ],
            "color_palette": "deep purples, electric blues, hot pinks, neon greens against dark shadows",
            "lighting": "harsh neon rim lighting, volumetric fog, god rays through smoke",
            "mood": "dystopian yet beautiful, melancholic, electric"
        },

        "hyperrealistic": {
            "description": "Photographic realism with cinematic lighting",
            "keywords": [
                "hyperrealistic", "photorealistic", "8K resolution", "ultra detailed",
                "film grain", "natural lighting", "perfect focus", "real-world textures",
                "authentic materials", "lifelike", "documentary style"
            ],
            "color_palette": "natural color grading, filmic tones, subtle contrast",
            "lighting": "natural three-point lighting, soft shadows, realistic reflections",
            "mood": "authentic, grounded, tangible"
        },

        "surreal_dreamscape": {
            "description": "Dream-like impossible geometries and floating elements",
            "keywords": [
                "surreal", "dreamlike", "impossible architecture", "floating objects",
                "MC Escher", "Salvador Dali inspired", "warped perspective",
                "ethereal", "otherworldly", "gravity-defying", "liminal space"
            ],
            "color_palette": "desaturated pastels, unexpected color combinations, shifting hues",
            "lighting": "impossible light sources, dreamy diffusion, soft ethereal glow",
            "mood": "uncanny, contemplative, mysterious"
        },

        "noir_cinematic": {
            "description": "Classic film noir with dramatic shadows and mystery",
            "keywords": [
                "film noir", "chiaroscuro", "venetian blind shadows", "smoke filled room",
                "black and white", "high contrast", "detective aesthetic", "femme fatale lighting",
                "1940s cinematography", "mystery", "dramatic shadows"
            ],
            "color_palette": "monochrome, deep blacks, bright whites, silver grays",
            "lighting": "harsh single-source lighting, venetian blind patterns, rim lighting",
            "mood": "mysterious, dramatic, tense"
        },

        "solarpunk_utopia": {
            "description": "Optimistic eco-future with nature and technology in harmony",
            "keywords": [
                "solarpunk", "vertical gardens", "sustainable tech", "solar panels",
                "green architecture", "hopeful future", "nature integrated", "clean energy",
                "bright and airy", "utopian", "eco-friendly"
            ],
            "color_palette": "vibrant greens, warm golds, sky blues, earth tones",
            "lighting": "natural sunlight, dappled through leaves, golden hour warmth",
            "mood": "hopeful, peaceful, harmonious"
        },

        "cosmic_horror": {
            "description": "Lovecraftian incomprehensible vastness and ancient terror",
            "keywords": [
                "cosmic horror", "eldritch", "incomprehensible scale", "ancient geometries",
                "void", "lovecraftian", "non-euclidean", "unfathomable depths",
                "celestial terror", "sanity-bending", "cosmic insignificance"
            ],
            "color_palette": "deep purples, void blacks, sickly greens, alien colors",
            "lighting": "unnatural bioluminescence, impossible light from nowhere, deep shadows",
            "mood": "dread, awe, insignificance"
        },

        "vaporwave_aesthetic": {
            "description": "80s/90s internet culture with glitch art and nostalgia",
            "keywords": [
                "vaporwave", "retrowave", "glitch art", "VHS distortion", "palm trees",
                "geometric shapes", "greek statues", "Windows 95", "pixel sorting",
                "A E S T H E T I C", "sunset grid", "chrome spheres"
            ],
            "color_palette": "hot pink, cyan, purple, sunset gradients, neon on black",
            "lighting": "sunset glow, neon strip lighting, CRT screen glow",
            "mood": "nostalgic, ironic, dreamlike"
        },

        "brutalist_architecture": {
            "description": "Raw concrete geometry with imposing scale",
            "keywords": [
                "brutalist", "raw concrete", "geometric forms", "monolithic",
                "stark", "imposing scale", "Soviet architecture", "angular",
                "utilitarian beauty", "industrial", "concrete texture"
            ],
            "color_palette": "concrete gray, rust orange, weathered metal, muted earth tones",
            "lighting": "harsh overhead sun, deep shadows, dramatic contrast",
            "mood": "imposing, austere, powerful"
        },

        "bioluminescent_nature": {
            "description": "Glowing organisms and natural light in darkness",
            "keywords": [
                "bioluminescence", "glowing organisms", "deep ocean", "fireflies",
                "phosphorescence", "natural glow", "bio-light", "jellyfish",
                "glowworms", "fungi glow", "northern lights"
            ],
            "color_palette": "electric blues, greens, teals against deep darkness",
            "lighting": "organic glow, soft bioluminescent light, darkness punctuated by life",
            "mood": "magical, serene, alien yet natural"
        },

        "studio_ghibli": {
            "description": "Whimsical hand-drawn animation with emotional depth",
            "keywords": [
                "Studio Ghibli style", "hand-drawn animation", "watercolor backgrounds",
                "whimsical", "emotional", "pastoral", "flying scenes", "food porn",
                "gentle magic", "environmental themes", "nostalgic"
            ],
            "color_palette": "soft pastels, vibrant greens, warm earth tones, sky blues",
            "lighting": "soft natural light, magical glow, sunset warmth, dappled shade",
            "mood": "whimsical, nostalgic, heartwarming"
        },

        "glitch_reality": {
            "description": "Reality breaking down into digital artifacts",
            "keywords": [
                "glitch art", "reality breaking", "pixel sorting", "data moshing",
                "RGB split", "scan lines", "digital corruption", "matrix glitches",
                "fragmented reality", "databending", "corrupted files"
            ],
            "color_palette": "chromatic aberration, RGB split, neon artifacts on black",
            "lighting": "flickering digital, scan line sweeps, corrupted brightness",
            "mood": "unsettling, digital, fragmented"
        },

        "macro_abstract": {
            "description": "Extreme close-ups revealing abstract beauty in the mundane",
            "keywords": [
                "macro photography", "extreme close-up", "abstract textures",
                "soap bubbles", "crystal formations", "water droplets", "fabric fibers",
                "insect eyes", "paint texture", "everyday objects as art"
            ],
            "color_palette": "iridescent, prismatic, natural material colors magnified",
            "lighting": "extreme close-up lighting, texture reveal, shallow depth of field",
            "mood": "intimate, revelatory, meditative"
        }
    }

    # ============================================================================
    # CAMERA TECHNIQUES - Professional cinematography
    # ============================================================================

    CAMERA_MOVEMENTS = {
        "establishing": [
            "slow crane up revealing scale",
            "drone ascending from ground to sky",
            "extreme wide establishing shot",
            "God's eye view straight down",
            "helicopter circle around subject",
            "pushing through environment reveal"
        ],

        "intimate": [
            "slow dolly push into subject",
            "macro close-up focus pull",
            "handheld intimate follow",
            "over-shoulder perspective",
            "extreme close-up detail",
            "first-person POV drift"
        ],

        "dynamic": [
            "whip pan reveal transition",
            "FPV drone racing through",
            "steadicam rapid follow",
            "360 degree spiral rotation",
            "vertigo dolly zoom effect",
            "tracking shot at high speed"
        ],

        "artistic": [
            "slow motion floating camera",
            "timelapse compression",
            "hyperlapse moving through time",
            "tilt-shift miniature effect",
            "rack focus depth transition",
            "parallax dolly zoom"
        ],

        "experimental": [
            "underwater fluid glide",
            "bullet time freeze rotation",
            "kaleidoscope rotation",
            "thermal imaging perspective",
            "X-ray vision transition",
            "microscope dive into detail"
        ]
    }

    # ============================================================================
    # LIGHTING SETUPS - Cinematic illumination
    # ============================================================================

    LIGHTING_STYLES = {
        "naturalistic": [
            "golden hour warm sunlight",
            "soft window light diffusion",
            "overcast even lighting",
            "dappled light through trees",
            "blue hour twilight glow"
        ],

        "dramatic": [
            "harsh single-source rim light",
            "chiaroscuro contrast",
            "venetian blind shadow patterns",
            "silhouette backlighting",
            "spotlight isolation"
        ],

        "atmospheric": [
            "volumetric god rays",
            "fog with backlighting",
            "underwater caustics",
            "dust particles in light beams",
            "atmospheric haze"
        ],

        "artificial": [
            "neon underglow",
            "LED strip accents",
            "holographic projections",
            "screen glow illumination",
            "laser light show"
        ],

        "magical": [
            "bioluminescent glow",
            "aurora borealis shimmer",
            "phosphorescent waves",
            "firefly sparkle",
            "magical particle glow"
        ]
    }

    # ============================================================================
    # COLOR GRADING - Professional post-production looks
    # ============================================================================

    COLOR_GRADES = {
        "cinematic": [
            "teal and orange blockbuster",
            "Blade Runner 2049 palette",
            "Christopher Nolan desaturated blues",
            "Wes Anderson pastel symmetry",
            "Denis Villeneuve muted earth tones"
        ],

        "vintage": [
            "faded Kodachrome film",
            "VHS tape degradation",
            "1970s warm film stock",
            "black and white silver gelatin",
            "Polaroid instant film fade"
        ],

        "modern": [
            "high contrast HDR",
            "flat LOG profile",
            "vibrant OLED colors",
            "minimal desaturation",
            "crisp digital clarity"
        ],

        "stylized": [
            "monochrome with color splash",
            "infrared false color",
            "split-toning dual temperature",
            "crushed blacks lifted highlights",
            "bleach bypass harsh contrast"
        ]
    }

    # ============================================================================
    # SUBJECTS & SCENES - What to film
    # ============================================================================

    SUBJECTS = {
        "natural": [
            "light refracting through water droplets",
            "smoke tendrils in still air",
            "ink dispersing in water",
            "silk fabric floating in wind",
            "sand dunes shifting",
            "ice crystals forming",
            "petals falling in slow motion",
            "fog rolling over landscape",
            "aurora borealis dancing",
            "bioluminescent waves crashing"
        ],

        "abstract": [
            "liquid metal flowing",
            "holographic shimmer on surfaces",
            "particle field simulation",
            "magnetic ferrofluid spikes",
            "soap bubble iridescence",
            "prism light diffraction",
            "plasma filaments",
            "caustic light patterns underwater",
            "volumetric fog with god rays",
            "chrome sphere reflections"
        ],

        "urban": [
            "neon reflections on wet pavement",
            "rain streaking down glass",
            "city lights bokeh blur",
            "steam rising from vents",
            "traffic light trails long exposure",
            "glass skyscraper reflections",
            "subway train motion blur",
            "graffiti wall art detail",
            "urban decay textures",
            "rooftop cityscape view"
        ],

        "cosmic": [
            "nebula cloud formations",
            "star field rotation",
            "black hole gravitational lensing",
            "supernova explosion shockwave",
            "galaxy spiral arms rotating",
            "planetary rings from above",
            "comet tail streaming",
            "solar prominence eruption",
            "pulsar lighthouse beam",
            "wormhole portal"
        ],

        "technological": [
            "circuit board macro detail",
            "fiber optic light transmission",
            "holographic data visualization",
            "quantum computing cooling",
            "robotic arm precision movement",
            "3D printer creating layers",
            "server farm LED patterns",
            "drone swarm coordination",
            "AR overlay interface",
            "neural network visualization"
        ]
    }

    # ============================================================================
    # MOODS & ATMOSPHERES - Emotional direction
    # ============================================================================

    MOODS = {
        "contemplative": [
            "serene and meditative",
            "peaceful introspection",
            "quiet solitude",
            "zen tranquility",
            "gentle melancholy"
        ],

        "energetic": [
            "electric and kinetic",
            "pulse-pounding intensity",
            "vibrant dynamism",
            "frenetic energy",
            "explosive power"
        ],

        "mysterious": [
            "enigmatic and cryptic",
            "haunting beauty",
            "eerie atmosphere",
            "uncanny valley",
            "hidden depths"
        ],

        "epic": [
            "awe-inspiring grandeur",
            "majestic scale",
            "sublime vastness",
            "heroic triumph",
            "transcendent beauty"
        ],

        "intimate": [
            "delicate fragility",
            "tender closeness",
            "whispered secrets",
            "vulnerable authenticity",
            "gentle reverence"
        ],

        "otherworldly": [
            "alien beauty",
            "cosmic insignificance",
            "reality-bending",
            "dreamlike impossibility",
            "liminal space unease"
        ]
    }

    # ============================================================================
    # AI PROMPT GENERATION - Let AI decide everything
    # ============================================================================

    def __init__(self, ai_generate_func):
        """
        Initialize cinematic director with AI generation function.

        Args:
            ai_generate_func: Function that takes a prompt and returns AI-generated text
        """
        self.generate_ai = ai_generate_func

    def generate_video_prompt(
        self,
        topic: Optional[str] = None,
        context: Optional[str] = None,
        force_style: Optional[str] = None
    ) -> str:
        """
        Generate a production-ready video prompt with AI making ALL creative decisions.

        Args:
            topic: Optional topic for context (NOT included in video)
            context: Optional additional context
            force_style: Optional style override (e.g., "cyberpunk")

        Returns:
            Complete Veo-optimized video prompt
        """

        # Step 1: AI decides the creative direction
        direction = self._ai_choose_direction(topic, context, force_style)

        # Step 2: AI generates the final prompt based on that direction
        final_prompt = self._ai_generate_final_prompt(direction)

        return final_prompt

    def _ai_choose_direction(
        self,
        topic: Optional[str],
        context: Optional[str],
        force_style: Optional[str]
    ) -> Dict:
        """
        Let AI analyze context and choose ALL creative direction.
        Returns dict with style, camera, lighting, subject, mood choices.
        """

        # Build available options for AI
        styles_list = list(self.VISUAL_STYLES.keys())
        camera_categories = list(self.CAMERA_MOVEMENTS.keys())
        lighting_categories = list(self.LIGHTING_STYLES.keys())
        subject_categories = list(self.SUBJECTS.keys())
        mood_categories = list(self.MOODS.keys())

        # If style is forced, use it
        if force_style and force_style.lower() in self.VISUAL_STYLES:
            chosen_style = force_style.lower()
        else:
            # Let AI choose or randomize if no AI
            chosen_style = random.choice(styles_list)

        direction_prompt = f"""You are a CINEMATIC DIRECTOR choosing the creative direction for a video.

CONTEXT (optional - video doesn't need to match this):
{context if context else 'Pure abstract art, no topic'}

AVAILABLE CREATIVE OPTIONS:

VISUAL STYLES:
{', '.join(styles_list)}

CAMERA MOVEMENT TYPES:
{', '.join(camera_categories)}

LIGHTING TYPES:
{', '.join(lighting_categories)}

SUBJECT TYPES:
{', '.join(subject_categories)}

MOOD TYPES:
{', '.join(mood_categories)}

YOUR JOB: Choose the BEST creative direction for a stunning 6-second video.
Think like a visionary director - what will be BEAUTIFUL and CAPTIVATING?

Respond in this EXACT format:
STYLE: [chosen style]
CAMERA_TYPE: [chosen camera category]
LIGHTING_TYPE: [chosen lighting category]
SUBJECT_TYPE: [chosen subject category]
MOOD_TYPE: [chosen mood category]
RATIONALE: [one sentence why this combo works]"""

        try:
            response = self.generate_ai(direction_prompt)

            # Parse AI response
            direction = {
                "style": self._parse_field(response, "STYLE", chosen_style),
                "camera_type": self._parse_field(response, "CAMERA_TYPE", "artistic"),
                "lighting_type": self._parse_field(response, "LIGHTING_TYPE", "atmospheric"),
                "subject_type": self._parse_field(response, "SUBJECT_TYPE", "abstract"),
                "mood_type": self._parse_field(response, "MOOD_TYPE", "contemplative"),
                "rationale": self._parse_field(response, "RATIONALE", "visually stunning")
            }

            logger.info(f"🎬 AI chose: {direction['style']} / {direction['mood_type']}")
            logger.info(f"   Rationale: {direction['rationale']}")

        except Exception as e:
            logger.warning(f"AI direction failed, using aesthetic defaults: {e}")
            # Fallback to random choices
            direction = {
                "style": chosen_style,
                "camera_type": random.choice(camera_categories),
                "lighting_type": random.choice(lighting_categories),
                "subject_type": random.choice(subject_categories),
                "mood_type": random.choice(mood_categories),
                "rationale": "aesthetic fallback"
            }

        return direction

    def _ai_generate_final_prompt(self, direction: Dict) -> str:
        """
        AI generates the final polished video prompt based on creative direction.
        """

        # Get specific options from direction
        style_info = self.VISUAL_STYLES.get(direction["style"], self.VISUAL_STYLES["hyperrealistic"])
        camera_options = self.CAMERA_MOVEMENTS.get(direction["camera_type"], self.CAMERA_MOVEMENTS["artistic"])
        lighting_options = self.LIGHTING_STYLES.get(direction["lighting_type"], self.LIGHTING_STYLES["atmospheric"])
        subject_options = self.SUBJECTS.get(direction["subject_type"], self.SUBJECTS["abstract"])
        mood_options = self.MOODS.get(direction["mood_type"], self.MOODS["contemplative"])

        # Pick specific examples
        camera = random.choice(camera_options)
        lighting = random.choice(lighting_options)
        subject = random.choice(subject_options)
        mood = random.choice(mood_options)

        final_prompt = f"""Create the FINAL VIDEO PROMPT for Veo AI video generation.

CREATIVE DIRECTION CHOSEN:
- Visual Style: {direction['style']}
- Description: {style_info['description']}
- Camera Movement: {camera}
- Lighting: {lighting}
- Subject: {subject}
- Mood: {mood}
- Color Palette: {style_info['color_palette']}

REQUIREMENTS FOR VEO:
- Single sentence, 120-200 characters
- Include: camera movement, subject, lighting, color palette, mood
- Technical and specific (not vague)
- NO text overlays, NO logos, NO faces
- Optimized for 6-second video generation
- Make it CINEMATIC and VISUALLY STUNNING

Output ONLY the final video prompt, nothing else:"""

        try:
            response = self.generate_ai(final_prompt)
            video_prompt = self._clean_prompt(response)

            if video_prompt and len(video_prompt) >= 50:
                logger.info(f"✅ Final prompt: {video_prompt}")
                return video_prompt

        except Exception as e:
            logger.warning(f"AI final prompt failed: {e}")

        # Fallback: construct manually
        fallback = (
            f"{camera.capitalize()}, {subject}, "
            f"{lighting}, {style_info['color_palette']}, "
            f"{mood}, cinematic, {direction['style']} aesthetic"
        )

        # Ensure length is good
        if len(fallback) > 200:
            fallback = fallback[:197] + "..."

        logger.info(f"📝 Using fallback prompt: {fallback}")
        return fallback

    def _parse_field(self, response: str, field: str, default: str) -> str:
        """Parse a field from AI response."""
        import re
        pattern = rf'{field}:\s*(.+?)(?:\n|$)'
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            value = match.group(1).strip().strip('"').strip("'")
            # Validate it's not too long
            if value and len(value) < 100:
                return value
        return default

    def _clean_prompt(self, response: str) -> str:
        """Clean AI-generated prompt."""
        # Remove common prefixes
        prefixes = ["VIDEO PROMPT:", "PROMPT:", "OUTPUT:", "FINAL:"]
        cleaned = response.strip()

        for prefix in prefixes:
            if cleaned.upper().startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()

        # Remove quotes and markdown
        cleaned = cleaned.strip('"').strip("'").strip('`').replace('**', '')

        # Get first sentence/line
        cleaned = cleaned.split('\n')[0].strip()

        # Check for failure keywords
        fail_words = ["cannot", "unable", "sorry", "error", "invalid"]
        if any(word in cleaned.lower() for word in fail_words):
            return ""

        return cleaned

    def get_random_style_showcase(self) -> str:
        """
        Generate a video prompt showcasing a random style.
        Useful for testing different aesthetics.
        """
        style_name = random.choice(list(self.VISUAL_STYLES.keys()))
        style_info = self.VISUAL_STYLES[style_name]

        camera = random.choice(self.CAMERA_MOVEMENTS["artistic"])
        subject = random.choice(self.SUBJECTS["abstract"])
        lighting = random.choice(self.LIGHTING_STYLES["atmospheric"])
        mood = random.choice(self.MOODS["contemplative"])

        prompt = (
            f"{camera.capitalize()}, {subject}, "
            f"{lighting}, {style_info['color_palette']}, "
            f"{mood}, cinematic {style_name} aesthetic"
        )

        return prompt
