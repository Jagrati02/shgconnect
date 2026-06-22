"""
Django management command to import cluster_results.csv into the database.

Usage:
    python manage.py import_clusters
    python manage.py import_clusters --csv path/to/cluster_results.csv
    python manage.py import_clusters --clear   (clears existing data first)
"""

import os
import csv
import re
from django.core.management.base import BaseCommand
from clusters.models import SHGCluster, SHGClusterMember


def _normalize_name(value):
    """Upper-case, trim, and collapse internal whitespace for name matching."""
    return re.sub(r'\s+', ' ', (value or '').strip().upper())


# ── Cluster label → human-readable name + description ──────────
CLUSTER_PROFILES = {
    0: {
        'name':        'Livestock Specialists',
        'livelihood':  'livestock',
        'description': 'SHGs specialising in animal husbandry — dairy, poultry, '
                       'goat farming. Well-suited for bulk orders of dairy products, '
                       'wool, and leather goods.',
    },
    1: {
        'name':        'Agriculture Producers',
        'livelihood':  'agriculture',
        'description': 'The largest cluster — crop farming SHGs producing rice, '
                       'wheat, pulses, and vegetables. High combined capacity '
                       'for bulk agricultural commodity orders.',
    },
    2: {
        'name':        'Manufacturing & Crafts',
        'livelihood':  'manufacturing',
        'description': 'SHGs producing handcrafted goods, textiles, food products, '
                       'and agro-processed items. Suited for bulk handicraft '
                       'and packaged food orders.',
    },
    3: {
        'name':        'Horticulture Growers',
        'livelihood':  'horticulture',
        'description': 'SHGs focused on fruits, vegetables, flowers, and '
                       'medicinal plants. Ideal for perishable bulk orders '
                       'with short lead times.',
    },
    4: {
        'name':        'Mixed / Emerging',
        'livelihood':  'unknown',
        'description': 'SHGs without a declared primary specialisation — often '
                       'newer or transitioning groups. High potential for '
                       'capacity building and category assignment.',
    },
    5: {
        'name':        'Trading & Commerce',
        'livelihood':  'trading',
        'description': 'Market-facing SHGs involved in retail, wholesale, '
                       'and commodity trading. Act as intermediaries '
                       'between producers and buyers.',
    },
    6: {
        'name':        'Fishery & Aquaculture',
        'livelihood':  'fishery',
        'description': 'SHGs in fish farming, inland fisheries, and '
                       'aquaculture. Suited for bulk seafood and '
                       'processed fish orders in coastal regions.',
    },
    7: {
        'name':        'Aggregation & Logistics',
        'livelihood':  'live_aggregation',
        'description': 'SHGs that aggregate produce from multiple producers '
                       'and facilitate bulk collection and dispatch. '
                       'Key nodes in the supply chain.',
    },
    8: {
        'name':        'Custom Hiring Services',
        'livelihood':  'custom_hiring',
        'description': 'SHGs providing equipment rental and custom hiring '
                       'services — tractors, threshers, irrigation equipment. '
                       'Support other SHGs\' production activities.',
    },
    9: {
        'name':        'Services & Support',
        'livelihood':  'services',
        'description': 'SHGs providing rural services — tailoring, beauty, '
                       'repair, education support. Smallest but growing '
                       'category with high income potential.',
    },
}


class Command(BaseCommand):
    help = 'Import cluster_results.csv into SHGCluster and SHGClusterMember tables'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv',
            type=str,
            default=None,
            help='Path to cluster_results.csv (default: ../data/cluster_results.csv)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing cluster data before importing',
        )

    def handle(self, *args, **options):

        # ── Resolve CSV path ──────────────────────────────────
        csv_path = options['csv']
        if not csv_path:
            base = os.path.dirname(os.path.abspath(__file__))
            csv_path = os.path.join(
                base, '..', '..', '..', '..', '..', 'data', 'cluster_results.csv'
            )
            csv_path = os.path.normpath(csv_path)

        if not os.path.exists(csv_path):
            self.stderr.write(
                self.style.ERROR(
                    f'File not found: {csv_path}\n'
                    f'Run: python manage.py import_clusters --csv /path/to/cluster_results.csv'
                )
            )
            return

        self.stdout.write(f'Reading: {csv_path}')

        # ── Optionally clear existing data ────────────────────
        if options['clear']:
            SHGClusterMember.objects.all().delete()
            SHGCluster.objects.all().delete()
            self.stdout.write(self.style.WARNING('Cleared existing cluster data.'))

        # ── Read CSV ─────────────────────────────────────────
        rows = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)

        self.stdout.write(f'Loaded {len(rows):,} rows from CSV')

        # ── Compute per-cluster stats ─────────────────────────
        from collections import defaultdict
        cluster_data = defaultdict(list)
        for row in rows:
            label = int(row['cluster_label'])
            cluster_data[label].append(row)

        # ── Create/update SHGCluster records ─────────────────
        self.stdout.write('Creating cluster records...')
        clusters_created = 0

        for label, members in sorted(cluster_data.items()):
            profile   = CLUSTER_PROFILES.get(label, {
                'name':        f'Cluster {label}',
                'livelihood':  'unknown',
                'description': '',
            })

            avg_members = sum(int(r['Active Members']) for r in members) / len(members)
            avg_savings = sum(float(r['Savings Amount']) for r in members) / len(members)
            total_cap   = sum(int(r['Active Members']) for r in members)

            cluster, created = SHGCluster.objects.update_or_create(
                label=label,
                defaults={
                    'name':               profile['name'],
                    'primary_livelihood': profile['livelihood'],
                    'description':        profile['description'],
                    'total_shgs':         len(members),
                    'avg_members':        round(avg_members, 2),
                    'avg_savings':        round(avg_savings, 2),
                    'total_capacity':     total_cap,
                    'silhouette_score':   0.5755,
                    'db_index':           0.3707,
                    'algorithm':          'K-Means',
                    'k_value':            10,
                },
            )
            clusters_created += 1
            status = 'Created' if created else 'Updated'
            self.stdout.write(
                f'  {status}: Cluster {label} — {profile["name"]} ({len(members):,} SHGs)'
            )

        # ── Create SHGClusterMember records (batch) ───────────
        self.stdout.write('Importing cluster members...')

        # Delete existing members to avoid duplicates
        SHGClusterMember.objects.all().delete()

        batch     = []
        batch_size = 500
        total     = 0

        cluster_map = {c.label: c for c in SHGCluster.objects.all()}

        for row in rows:
            label   = int(row['cluster_label'])
            cluster = cluster_map.get(label)
            if not cluster:
                continue

            member = SHGClusterMember(
                cluster             = cluster,
                shg_code            = str(row.get('SHG Code', '')),
                shg_name            = str(row.get('SHG Name', '')),
                state               = str(row.get('State', '')),
                district            = str(row.get('District', '')),
                block               = str(row.get('Block', '')),
                primary_livelihood  = str(row.get('Primary Livelihoods', '')),
                secondary_livelihood = str(row.get('Secondary Livelihoods', '')),
                active_members      = int(float(row.get('Active Members', 0))),
                savings_amount      = float(row.get('Savings Amount', 0)),
                shg_category        = str(row.get('SHG Category', '')),
                is_synthetic        = False,
            )
            batch.append(member)
            total += 1

            if len(batch) >= batch_size:
                SHGClusterMember.objects.bulk_create(batch)
                batch = []
                self.stdout.write(f'  Imported {total:,} rows...', ending='\r')
                self.stdout.flush()

        # Insert remaining
        if batch:
            SHGClusterMember.objects.bulk_create(batch)

        # ── Link registered SHG profiles to their cluster member ──
        linked = self._link_profiles()

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f'\n Import complete!\n'
                f'   Clusters created: {clusters_created}\n'
                f'   Members imported: {total:,}\n'
                f'   Profiles linked:  {linked}\n'
                f'\nRun: python manage.py runserver\n'
                f'Visit: /clusters/ to see results'
            )
        )

    def _link_profiles(self):
        """
        Populate SHGClusterMember.shg_profile for SHGs that are registered in
        the Django DB. Matching is resolved in priority order:
          1. SHGProfile.shg_id  ==  member.shg_code   (strongest)
          2. normalised SHG name match, preferring the same state

        Each profile links to at most one member and each member to at most one
        profile (the FK is OneToOne), so links are tracked to avoid reuse.
        Re-running is safe: members are recreated each import, so links are
        rebuilt from scratch.
        """
        from users.models import SHGProfile

        profiles = list(SHGProfile.objects.all())
        if not profiles:
            self.stdout.write('No registered SHG profiles to link.')
            return 0

        self.stdout.write('Linking registered SHG profiles to cluster members...')

        by_code = {}
        by_name = {}
        for m in SHGClusterMember.objects.all():
            code = str(m.shg_code).strip()
            if code:
                by_code.setdefault(code, m)
            name_key = _normalize_name(m.shg_name)
            if name_key:
                by_name.setdefault(name_key, []).append(m)

        linked     = 0
        used_member = set()

        for p in profiles:
            member = None

            # 1. strong match on code
            code = str(p.shg_id).strip()
            cand = by_code.get(code)
            if cand is not None and cand.id not in used_member:
                member = cand

            # 2. name match (prefer same state)
            if member is None:
                candidates = [
                    c for c in by_name.get(_normalize_name(p.shg_name), [])
                    if c.id not in used_member
                ]
                if candidates:
                    same_state = [
                        c for c in candidates
                        if _normalize_name(c.state) == _normalize_name(p.state)
                    ]
                    member = same_state[0] if same_state else candidates[0]

            if member is not None:
                member.shg_profile = p
                member.save(update_fields=['shg_profile'])
                used_member.add(member.id)
                linked += 1

        self.stdout.write(
            f'  Linked {linked} of {len(profiles)} registered SHG profiles.'
        )
        return linked