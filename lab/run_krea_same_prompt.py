"""Run the same scene prompt through the deployed Krea 2 Modal test app."""

import modal


app = modal.App("local-image-gen-same-prompt")


@app.local_entrypoint()
def main() -> None:
    prompt = (
        "Use the attached image as a reference for the visual mood and composition. "
        "Generate a new photorealistic cinematic portrait, not an exact copy: a young "
        "Korean woman in a soft cream knit sweater sitting by a rain-covered cafe window "
        "at night, close-up three-quarter framing, her face centered slightly right, "
        "shallow depth of field. Preserve the striking mix of cool cyan and deep blue "
        "reflections across the glass with warm amber and orange neon bokeh behind her, "
        "visible raindrops and fine skin and hair texture, natural soft expression, "
        "intimate melancholic atmosphere, high-end 35mm photography, realistic optics, "
        "subtle film grain. Keep the same square composition and strong neon color contrast. "
        "No text, logos, watermark, or duplicated facial features."
    )
    worker = modal.Cls.from_name("local-image-gen-modal-test", "ImageGen")()
    print(worker.generate.remote("krea2", prompt, 1024, 1024, 12003))
