"""
Seed the marketplace with demo SHGs and a varied product catalogue.

Creates a handful of SHG accounts whose names/states/codes are taken from the
real clustered dataset (cluster_results.csv) — so that:
  * `import_clusters` links them to their cluster (shg_id == shg_code), and
  * product categories map to cluster livelihoods, making the proportional
    allocation routing and "Place Cluster Order" flow work end-to-end.

A styled placeholder image is generated for every product with Pillow.

Usage:
    python manage.py seed_marketplace
    python manage.py seed_marketplace --fresh   (remove previously seeded demo
                                                 data first, then re-seed)

All seeded SHG logins use the email shown in the summary and password
"demo12345". Seeded accounts are marked by the @demo.shgconnect email domain so
--fresh only ever removes demo data, never real users.
"""

import os
import csv
from collections import Counter, defaultdict

from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth.models import User

from users.models import SHGProfile
from products.models import Product, Category

from PIL import Image, ImageDraw, ImageFont


DEMO_DOMAIN = 'demo.shgconnect'
DEMO_PASSWORD = 'demo12345'

# Per-livelihood colour palette (top → bottom gradient) for the image tiles.
PALETTES = {
    'livestock':     ((201, 162, 39),  (120, 85, 20)),
    'agriculture':   ((58, 125, 68),   (26, 74, 40)),
    'manufacturing': ((142, 68, 173),  (84, 40, 105)),
    'horticulture':  ((230, 126, 34),  (160, 75, 18)),
    'fishery':       ((41, 128, 185),  (20, 70, 110)),
    'trading':       ((192, 57, 43),   (110, 30, 25)),
    'default':       ((90, 90, 90),    (40, 40, 40)),
}

# Featured livelihoods → category name + product catalogue. Category names and
# tags contain keywords that clusters/allocation.py maps to the livelihood.
CATALOGUE = {
    'livestock': {
        'email':    f'dairy@{DEMO_DOMAIN}',
        'category': 'Dairy & Livestock',
        'products': [
            ('Farm Fresh Cow Ghee',   'Pure hand-churned cow ghee, 500g jar.',        650, 'jar',  120, 580, 10, 'dairy, ghee, livestock'),
            ('Organic Paneer',        'Fresh full-cream paneer made daily, 1kg.',     320, 'kg',   80,  290, 5,  'dairy, paneer, livestock'),
            ('Free-Range Eggs (30)',  'Tray of 30 free-range desi eggs.',             240, 'tray', 200, 210, 4,  'egg, poultry, livestock'),
            ('Natural Wool Yarn',     'Hand-spun sheep wool yarn, 250g skein.',       420, 'skein',60,  380, 6,  'wool, livestock'),
        ],
    },
    'agriculture': {
        'email':    f'grains@{DEMO_DOMAIN}',
        'category': 'Grains & Pulses',
        'products': [
            ('Organic Basmati Rice',  'Aromatic long-grain basmati, 5kg pack.',       560, 'pack', 150, 520, 10, 'rice, grain, agriculture'),
            ('Whole Wheat Flour',     'Stone-ground whole wheat atta, 10kg.',         480, 'bag',  120, 440, 8,  'wheat, grain, agriculture'),
            ('Toor Dal (Pulses)',     'Unpolished toor dal, 2kg pack.',               360, 'pack', 100, 330, 6,  'pulse, dal, agriculture'),
            ('Cold-Pressed Mustard Oil','Wood-pressed mustard oil, 1L bottle.',       290, 'bottle',90, 260, 6,  'mustard, crop, agriculture'),
        ],
    },
    'manufacturing': {
        'email':    f'crafts@{DEMO_DOMAIN}',
        'category': 'Handicrafts & Textiles',
        'products': [
            ('Handwoven Cotton Saree','Pure handloom cotton saree with zari border.', 1450,'piece',40,  1300,3,  'handloom, textile, handicraft'),
            ('Terracotta Pottery Set','Hand-painted terracotta dinner set of 6.',     980, 'set',  35,  890, 3,  'pottery, handicraft, craft'),
            ('Jute Handbag',          'Eco-friendly embroidered jute handbag.',       540, 'piece',70,  490, 5,  'jute, handicraft, craft'),
            ('Block-Print Bedsheet',  'Hand block-printed cotton double bedsheet.',   860, 'piece',55,  780, 4,  'textile, cloth, handicraft'),
        ],
    },
    'horticulture': {
        'email':    f'orchard@{DEMO_DOMAIN}',
        'category': 'Fruits & Flowers',
        'products': [
            ('Alphonso Mango Pulp',   'Sweet Alphonso mango pulp, 1kg tin.',          380, 'tin',  90,  340, 6,  'fruit, mango, horticulture'),
            ('Dried Hibiscus Flowers','Sun-dried hibiscus for tea, 200g.',            260, 'pack', 70,  230, 5,  'flower, herb, horticulture'),
            ('Fresh Marigold Garland','Festive marigold flower garlands.',            120, 'piece',300, 100, 10, 'flower, marigold, horticulture'),
            ('Amla Candy',            'Sun-dried sweet amla (gooseberry) candy, 500g.',300,'pack', 80,  270, 6,  'fruit, amla, horticulture'),
        ],
    },
    'fishery': {
        'email':    f'fishery@{DEMO_DOMAIN}',
        'category': 'Fishery Products',
        'products': [
            ('Dried Bombay Duck',     'Traditional sun-dried fish, 250g pack.',       340, 'pack', 80,  300, 6,  'fish, dried, fishery'),
            ('Prawn Pickle',          'Spicy prawn pickle in oil, 400g jar.',         420, 'jar',  60,  380, 5,  'prawn, fish, fishery'),
            ('Fish Curry Masala',     'Coastal fish-curry spice blend, 200g.',        180, 'pack', 120, 160, 6,  'fish, masala, fishery'),
        ],
    },
}


def _resolve_csv(path):
    if path:
        return path
    return os.path.join(settings.BASE_DIR.parent, 'data', 'cluster_results.csv')


def _font(size, bold=True):
    candidates = (['C:/Windows/Fonts/arialbd.ttf', 'arialbd.ttf'] if bold
                  else ['C:/Windows/Fonts/arial.ttf', 'arial.ttf'])
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ''
    for w in words:
        trial = (cur + ' ' + w).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _make_image(out_path, title, subtitle, livelihood):
    W, H = 800, 600
    c1, c2 = PALETTES.get(livelihood, PALETTES['default'])
    img = Image.new('RGB', (W, H), c1)
    d = ImageDraw.Draw(img)

    # vertical gradient
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)],
               fill=tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)))

    # badge with the product's initial
    cx, cy, r = W // 2, 210, 78
    light = tuple(min(255, c1[i] + 60) for i in range(3))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=light)
    initial = (title[:1] or '?').upper()
    fbig = _font(96)
    bb = d.textbbox((0, 0), initial, font=fbig)
    d.text((cx - (bb[2] - bb[0]) / 2, cy - (bb[3] - bb[1]) / 2 - bb[1]),
           initial, font=fbig, fill=(255, 255, 255))

    # title (wrapped) + subtitle
    ftitle = _font(46)
    y = 350
    for line in _wrap(d, title, ftitle, W - 120):
        bb = d.textbbox((0, 0), line, font=ftitle)
        d.text(((W - (bb[2] - bb[0])) / 2, y), line, font=ftitle, fill=(255, 255, 255))
        y += 56
    fsub = _font(28, bold=False)
    bb = d.textbbox((0, 0), subtitle, font=fsub)
    d.text(((W - (bb[2] - bb[0])) / 2, H - 70), subtitle, font=fsub, fill=(255, 255, 255))

    img.save(out_path, 'PNG')


class Command(BaseCommand):
    help = 'Seed demo SHGs and a varied product catalogue (with images).'

    def add_arguments(self, parser):
        parser.add_argument('--csv', type=str, default=None,
                            help='Path to cluster_results.csv (default: ../data/...).')
        parser.add_argument('--fresh', action='store_true',
                            help='Remove previously seeded demo data first.')

    def handle(self, *args, **options):
        if options['fresh']:
            qs = User.objects.filter(email__endswith=f'@{DEMO_DOMAIN}')
            n = qs.count()
            qs.delete()   # cascades to SHGProfile + Product
            self.stdout.write(self.style.WARNING(f'Removed {n} seeded demo SHG(s) and their products.'))

        csv_path = _resolve_csv(options['csv'])
        if not os.path.exists(csv_path):
            self.stderr.write(self.style.ERROR(f'CSV not found: {csv_path}'))
            return

        # group dataset rows by livelihood to pick real SHG identities
        by_livelihood = defaultdict(list)
        with open(csv_path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                by_livelihood[(row.get('Primary Livelihoods') or '').strip()].append(row)

        media_dir = os.path.join(settings.MEDIA_ROOT, 'product_images')
        os.makedirs(media_dir, exist_ok=True)

        total_shgs = total_products = 0
        summary = []
        used_states = set()   # spread SHGs across states for variety

        for livelihood, spec in CATALOGUE.items():
            rows = by_livelihood.get(livelihood, [])
            if not rows:
                self.stdout.write(self.style.WARNING(
                    f'No dataset rows for "{livelihood}" — skipping.'))
                continue

            # pick a real SHG in a distinct, well-populated state for variety
            # (still enough same-state members for the allocation partner pool)
            state_counts = Counter(r['State'] for r in rows).most_common()
            chosen_state = next(
                (st for st, cnt in state_counts if cnt >= 20 and st not in used_states),
                state_counts[0][0])
            used_states.add(chosen_state)
            pick = next(r for r in rows if r['State'] == chosen_state)

            user, _ = User.objects.get_or_create(
                username=spec['email'],
                defaults={'email': spec['email'],
                          'first_name': pick['SHG Name'].title()})
            user.set_password(DEMO_PASSWORD)
            user.email = spec['email']
            user.save()

            profile, _ = SHGProfile.objects.get_or_create(
                user=user,
                defaults={'shg_id': str(pick['SHG Code'])})
            profile.shg_id           = str(pick['SHG Code'])
            profile.shg_name         = pick['SHG Name'].title()
            profile.state            = pick['State'].title()
            profile.district         = pick['District'].title()
            profile.product_category = livelihood
            profile.members_count    = int(float(pick.get('Active Members') or 10))
            profile.production_capacity = profile.members_count
            profile.verified         = True
            profile.save()
            total_shgs += 1

            category, _ = Category.objects.get_or_create(name=spec['category'])

            for (name, desc, price, unit, qty, bulk, moq, tags) in spec['products']:
                product, _ = Product.objects.get_or_create(
                    shg=profile, name=name,
                    defaults={'description': desc, 'price': price})
                product.category           = category
                product.description        = desc
                product.price              = price
                product.bulk_price         = bulk
                product.quantity_available = qty
                product.unit               = unit
                product.min_order_qty      = moq
                product.lead_time_days     = 7
                product.state              = profile.state
                product.tags               = tags
                product.cluster_enabled    = True
                product.forecast_enabled   = False
                product.is_active          = True

                fname = f'demo_{livelihood}_{product.pk or abs(hash(name)) % 100000}.png'
                _make_image(os.path.join(media_dir, fname),
                            name, f"{profile.shg_name} · {profile.state}", livelihood)
                product.image = f'product_images/{fname}'
                product.save()
                total_products += 1

            summary.append((spec['email'], profile.shg_name, profile.state,
                            len(spec['products'])))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Seeded {total_shgs} SHG(s) and {total_products} product(s).'))
        self.stdout.write(f'Login password for all demo SHGs: {DEMO_PASSWORD}')
        for email, shg_name, state, n in summary:
            self.stdout.write(f'  {email:28s} {shg_name} ({state}) — {n} products')
        self.stdout.write('\nTip: run "python manage.py import_clusters" to link '
                           'these SHGs to their clusters.')
