---
title: "Video Production Automation"
description: Practical guide for automating video production and documentation using Python (Manim, MoviePy, OpenCV) and other tools.
location: .agent/skills/video-production-automation.md
agent_priority: Standard
last_updated: 2026-03-08
---

# Video Production & Automation Skills

[Back to README](../../README.md)

**🔗 Related Video Production Skills:**
- [Video Blender Automation](video-blender-automation.md) - 3D automation with Python
- [Video Manim Math](video-manim-math.md) - Mathematical animations
- [Video Remotion React](video-remotion-react.md) - Programmatic video with React
- [Video Resolve Editing](video-resolve-editing.md) - DaVinci Resolve API & timeline automation
- [Video Stick Figure](video-stick-figure.md) - 2D animation & physics

This skill details how to use Python libraries and external tools to create high-quality, automated video documentation and showcases for your Agentic Coding projects.

## 1. The Python Video Stack

### 1.1 Manim (Mathematical Animation Engine)
Best for: **Explaining concepts, algorithms, and logic flow.**
*   **Installation:** `pip install manim` (requires ffmpeg and latex).
*   **Key Concept:** Everything is a `Mobject` (Math Object). You animate them using `Play()`.
*   **Code Snippet (Basic Scene):**
    ```python
    from manim import *

    class AgentFlow(Scene):
        def construct(self):
            # Create nodes
            user = Text("User").set_color(BLUE)
            agent = Text("Agent").set_color(GREEN).next_to(user, RIGHT, buff=2)
            
            # Animate
            self.play(Write(user))
            self.play(Write(agent))
            self.play(Arrow(user.get_right(), agent.get_left()))
            self.wait(1)
    ```

### 1.2 MoviePy (Video Editing)
Best for: **Stitching clips, adding audio, and simple cuts.**
*   **Installation:** `pip install moviepy`
*   **Key Concept:** `VideoFileClip` is your main object. Use `subclip`, `concatenate_videoclips`, and `write_videofile`.
*   **Code Snippet (Simple Edit):**
    ```python
    from moviepy.editor import VideoFileClip, concatenate_videoclips

    # Load clips
    clip1 = VideoFileClip("recording_1.mp4").subclip(0, 5) # First 5 seconds
    clip2 = VideoFileClip("recording_2.mp4").subclip(0, 5)

    # Combine
    final_clip = concatenate_videoclips([clip1, clip2])
    final_clip.write_videofile("showcase.mp4")
    ```

### 1.3 OpenCV & PyAutoGUI (Screen Recording & Automation)
Best for: **Automating the demo itself.** Use PyAutoGUI to drive the mouse/keyboard and OpenCV to record the screen.
*   **Installation:** `pip install opencv-python pyautogui numpy`
*   **Strategy:**
    1.  Define a script for the "User" actions (typing commands).
    2.  Use `pyautogui.typewrite()` to simulate typing.
    3.  Use `cv2.VideoWriter` to capture frames (or use a dedicated screen recorder like OBS and just automate inputs).

## 2. The "Pro" Visual Stack (Non-Python)

For "Viral" quality usage, Python tools might be too stiff. Use these for polish:

### 2.1 Screen Studio (macOS)
*   **Why:** Automatically zooms into the mouse, adds motion blur, and smooths out jerky movements.
*   **Workflow:** Record your screen while PyAutoGUI runs your script. The result looks manually edited.

### 2.2 Adobe After Effects
*   **Why:** For high-end composite shots (e.g., 3D phone mockups, complex UI overlays).

## 3. Automation Workflow for Showcases

1.  **Scripting:** Write a `demo_script.py` using PyAutoGUI to perform the coding task live.
2.  **Recording:**
    *   *Option A (High Quality):* Run Screen Studio, then run `python demo_script.py`.
    *   *Option B (Fully Automated):* Use OpenCV to capture the screen while the script runs.
3.  **Editing:** Use MoviePy to trim silence, speed up long processing times (e.g., `clip.fx(vfx.speedx, 2)`), and add intro/outro.
4.  **Overlay:** Use Manim to generate an overlay video (with transparent background) explaining the logic, then composite it on top using MoviePy.

## 🔗 Related Video Skills

- [Video Blender Automation](video-blender-automation.md)
- [Video Manim Math](video-manim-math.md)
- [Video Production Automation](video-production-automation.md)
- [Video Remotion React](video-remotion-react.md)
- [Video Resolve Editing](video-resolve-editing.md)
- [Video Stick Figure](video-stick-figure.md)

---
[Back to README](../../README.md)
