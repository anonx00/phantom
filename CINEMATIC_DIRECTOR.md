# Cinematic Director - AI Video Prompt Generation

## Overview

The **CinematicDirector** gives your AI **FULL creative control** over video generation. It decides:

- 🎨 **Visual Style** (cyberpunk, hyperrealistic, surreal, noir, etc.)
- 🎥 **Camera Movements** (dolly push, FPV drone, vertigo zoom, etc.)
- 💡 **Lighting** (neon underglow, god rays, chiaroscuro, etc.)
- 🎭 **Mood** (contemplative, energetic, mysterious, epic, etc.)
- 🌈 **Color Grading** (teal & orange, Blade Runner palette, etc.)

## Production-Ready Features

### 12 Visual Styles

1. **cyberpunk** - Neon-soaked dystopian future (Blade Runner aesthetic)
2. **hyperrealistic** - Photographic realism with cinematic lighting
3. **surreal_dreamscape** - Dream-like impossible geometries
4. **noir_cinematic** - Classic film noir with dramatic shadows
5. **solarpunk_utopia** - Optimistic eco-future
6. **cosmic_horror** - Lovecraftian incomprehensible vastness
7. **vaporwave_aesthetic** - 80s/90s internet culture nostalgia
8. **brutalist_architecture** - Raw concrete geometry
9. **bioluminescent_nature** - Glowing organisms in darkness
10. **studio_ghibli** - Whimsical hand-drawn animation
11. **glitch_reality** - Reality breaking into digital artifacts
12. **macro_abstract** - Extreme close-ups revealing beauty

### Camera Techniques

- **Establishing**: Crane ups, drone ascents, God's eye views
- **Intimate**: Dolly pushes, macro close-ups, handheld follows
- **Dynamic**: Whip pans, FPV racing, vertigo zooms
- **Artistic**: Slow motion, timelapse, tilt-shift
- **Experimental**: Underwater glides, bullet time, kaleidoscope

### Lighting Styles

- **Naturalistic**: Golden hour, soft window light, dappled shade
- **Dramatic**: Chiaroscuro, rim lighting, silhouettes
- **Atmospheric**: Volumetric god rays, fog, caustics
- **Artificial**: Neon underglow, LED strips, holograms
- **Magical**: Bioluminescence, aurora, fireflies

## How It Works

### 1. AI Chooses Direction

The AI analyzes your topic and decides:
```
STYLE: cyberpunk
CAMERA_TYPE: dynamic
LIGHTING_TYPE: artificial
SUBJECT_TYPE: urban
MOOD_TYPE: energetic
RATIONALE: Perfect for high-tech content with visual impact
```

### 2. AI Generates Final Prompt

Based on the direction, AI creates a detailed Veo prompt:
```
FPV drone racing through neon-lit city, rain-soaked streets reflecting
purple and cyan lights, harsh rim lighting, electric and kinetic mood,
cyberpunk aesthetic, volumetric fog
```

## Integration

Already integrated! Your bot automatically uses CinematicDirector:

```python
# In meme_fetcher.py ContentResearcher
video_prompt = self.cinematic_director.generate_video_prompt(
    topic=topic,
    context=context,
    force_style="cyberpunk"  # Optional: force a specific style
)
```

## Force Specific Styles

You can force specific aesthetics:

```python
# Force cyberpunk
video_prompt = director.generate_video_prompt(force_style="cyberpunk")

# Force hyperrealistic
video_prompt = director.generate_video_prompt(force_style="hyperrealistic")

# Force surreal
video_prompt = director.generate_video_prompt(force_style="surreal_dreamscape")

# Let AI decide (default)
video_prompt = director.generate_video_prompt()
```

## Style Vocabulary

### Cyberpunk
- **Colors**: Deep purples, electric blues, hot pinks, neon greens
- **Lighting**: Harsh neon rim lighting, volumetric fog
- **Keywords**: Blade Runner, dystopian, tech noir, chrome

### Hyperrealistic
- **Colors**: Natural color grading, filmic tones
- **Lighting**: Natural three-point lighting, soft shadows
- **Keywords**: Photorealistic, 8K, film grain, authentic

### Vaporwave
- **Colors**: Hot pink, cyan, purple, sunset gradients
- **Lighting**: Sunset glow, neon strips, CRT screen glow
- **Keywords**: Retrowave, glitch art, A E S T H E T I C

### Studio Ghibli
- **Colors**: Soft pastels, vibrant greens, warm earth tones
- **Lighting**: Soft natural light, magical glow, sunset warmth
- **Keywords**: Whimsical, hand-drawn, nostalgic

## Example Prompts Generated

### Cyberpunk Style
```
Whip pan through neon-soaked alleyway, rain streaking down glass,
harsh purple and cyan rim lighting, chrome reflections on wet pavement,
dystopian yet beautiful mood, Blade Runner aesthetic
```

### Hyperrealistic Style
```
Slow dolly push macro close-up, water droplets on metallic surface,
natural three-point lighting revealing texture, 8K ultra detailed,
photorealistic film grain, serene and meditative mood
```

### Surreal Dreamscape
```
Floating camera through impossible architecture, warped perspective
MC Escher geometry, ethereal diffusion lighting, desaturated pastels,
uncanny and contemplative atmosphere
```

## Budget Optimization

- Uses Gemini Flash models (cheap)
- 2 AI calls per video prompt (direction + final prompt)
- ~$0.0001 per prompt (negligible cost)
- Legacy fallback if AI fails (no cost)

## Monitoring

Check logs for creative decisions:
```
🎬 AI chose: cyberpunk / energetic
   Rationale: High-tech content needs visual impact
✅ Final prompt: FPV drone racing through neon-lit city...
```

## Tips for Best Results

1. **Let AI decide** - Don't force styles unless needed
2. **Trust the process** - AI knows what looks good
3. **Mix it up** - Different styles keep content fresh
4. **Check logs** - Learn what AI is choosing

## Future Enhancements

- [ ] User preference learning (remember what performed well)
- [ ] Trend-based style selection (match current aesthetic trends)
- [ ] Advanced color theory (complementary palettes)
- [ ] Music/audio suggestions (match visual vibe)

---

**Status**: ✅ Production-Ready | Fully Integrated | AI-Autonomous
