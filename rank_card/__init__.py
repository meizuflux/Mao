import os
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont


class Generator:
    def __init__(self):
        self.default_bg = os.path.join('assets', 'card.jpg')
        self.font1 = os.path.join('assets', 'font.ttf')

    def generate_profile(self, profile_image: str = None, level: int = 1, current_xp: int = 0,
                         user_xp: int = 20, next_xp: int = 100, user_position: int = 1,
                         user_name: str = 'ppotatoo#9688'):

        card = Image.open(self.default_bg).convert("RGBA")

        profile_bytes = BytesIO(requests.get(profile_image).content)
        profile = Image.open(profile_bytes)
        profile = profile.convert('RGBA').resize((180, 180))

        profile_pic_holder = Image.new(
            "RGBA", card.size, (255, 255, 255, 0)
        )  # Is used for a blank image so that i can mask

        # Mask to crop image
        mask = Image.new("RGBA", card.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse(
            (29, 29, 209, 209), fill=(255, 25, 255, 255)
        )  # The part need to be cropped

        font_normal = ImageFont.truetype(self.font1, 36)
        font_small = ImageFont.truetype(self.font1, 20)

        black = (0, 0, 0)
        white = 189, 195, 199
        dark = (252, 179, 63)
        yellow = (255, 234, 167)

        def get_str(xp):
            if xp < 1000:
                return str(xp)
            if 1000 <= xp < 1000000:
                return str(round(xp / 1000, 1)) + "k"
            if xp > 1000000:
                return str(round(xp / 1000000, 1)) + "M"

        draw = ImageDraw.Draw(card)
        draw.text((245, 22), user_name, black, font=font_normal)
        draw.text((245, 98), f"Rank #{user_position}", black, font=font_small)
        draw.text((245, 123), f"Level {level}", black, font=font_small)
        draw.text(
            (245, 150),
            f"Exp {get_str(user_xp)}/{get_str(next_xp)}",
            black,
            font=font_small,
        )

        blank = Image.new("RGBA", card.size, (255, 255, 255, 0))
        blank_draw = ImageDraw.Draw(blank)
        blank_draw.rectangle(
            (245, 185, 750, 205), fill=(255, 255, 255, 0), outline=black
        )

        xp_needed = next_xp - current_xp
        userxp = user_xp - current_xp

        current_percentage = (userxp / xp_needed) * 100
        length_of_bar = (current_percentage * 4.9) + 248

        blank_draw.rectangle((248, 188, length_of_bar, 202), fill=black)
        blank_draw.ellipse((20, 20, 218, 218), fill=(255, 255, 255, 0), outline=black)

        profile_pic_holder.paste(profile, (29, 29, 209, 209))

        pre = Image.composite(profile_pic_holder, card, mask)
        pre = Image.alpha_composite(pre, blank)

        final = Image.alpha_composite(pre, blank)
        final_bytes = BytesIO()
        final.save(final_bytes, 'png')
        final_bytes.seek(0)
        return final_bytes
