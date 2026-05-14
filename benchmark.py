#!/usr/bin/env python3
"""
COS 730 Assignment 2 — Task 6 Benchmark
Empirically compares the baseline and optimised implementations across:
  - Execution time (submission flow, evaluation flow)
  - Domain method call count (instrumented wrappers)
  - Total Python function call count (sys.settrace)
  - Database connection count
  - Static code metrics (AST-parsed LOC, public methods, cyclomatic complexity)

Run from the project root: python3 benchmark.py
Graphs are saved to ./graphs/
"""

import sys, os, time, sqlite3, tempfile, gc, statistics, ast, types
from unittest.mock import patch

ROOT = os.path.dirname(os.path.abspath(__file__))
GRAPHS_DIR = os.path.join(ROOT, 'graphs')
os.makedirs(GRAPHS_DIR, exist_ok=True)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

plt.rcParams.update({
    'font.size': 11,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'figure.dpi': 150,
})

BASELINE_COL = '#e74c3c'
OPT_COL      = '#27ae60'
BASELINE_LBL = 'Baseline'
OPT_LBL      = 'Optimised'

# ─── helpers ──────────────────────────────────────────────────────────────────

def load_impl(folder):
    """Import database + controllers from a subfolder without polluting sys.modules."""
    path = os.path.join(ROOT, folder)
    for mod in ['database', 'controllers']:
        sys.modules.pop(mod, None)
    sys.path.insert(0, path)
    import database, controllers
    sys.path.pop(0)
    db_mod   = sys.modules.pop('database')
    ctrl_mod = sys.modules.pop('controllers')
    return db_mod, ctrl_mod


def setup_db(db_mod):
    """Create a temp SQLite file, patch DB_NAME, and initialise the schema."""
    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp.close()
    db_mod.DB_NAME = tmp.name
    db_mod.init_db()
    return tmp.name


def instrument(obj, method_names):
    """Wrap methods on obj with a counter. Returns a dict name→count."""
    counts = {m: 0 for m in method_names}
    originals = {}
    for name in method_names:
        orig = getattr(obj, name)
        originals[name] = orig
        def make_wrapper(n, fn):
            def wrapper(*a, **kw):
                counts[n] += 1
                return fn(*a, **kw)
            return wrapper
        setattr(obj, name, make_wrapper(name, orig))
    return counts, originals


def restore(obj, originals):
    for name, fn in originals.items():
        setattr(obj, name, fn)


class TraceCounter:
    """Count total Python function calls via sys.settrace."""
    def __init__(self):
        self.n = 0
    def __enter__(self):
        self.n = 0
        sys.settrace(self._trace)
        return self
    def __exit__(self, *_):
        sys.settrace(None)
    def _trace(self, frame, event, arg):
        if event == 'call':
            self.n += 1
        return self._trace


FAKE_BYTES = b'%PDF-1.7 fake content for benchmarking ' * 50

def make_data(i):
    return {
        'title': f'Research Paper {i}',
        'author': f'Author {i}',
        'email': f'author{i}@example.com',
        'file_bytes': FAKE_BYTES,
        'file_name': f'paper_{i}.pdf',
    }


def submit_one(ctrl_mod, data, idx):
    with patch.object(ctrl_mod, 'upload_to_r2', return_value=f'/bench/paper_{idx}.pdf'):
        return ctrl_mod.SubmissionController().submit(data)


def get_reviewer_ids(db_mod, submission_id):
    conn = db_mod.get_db_connection()
    cur  = conn.cursor()
    cur.execute('SELECT reviewer_id FROM reviews WHERE submission_id = ?', (submission_id,))
    ids = [r[0] for r in cur.fetchall()]
    conn.close()
    return ids


# ─── load implementations ─────────────────────────────────────────────────────

print("Loading implementations …")
init_db, init_ctrl = load_impl('initial-implementation')
opt_db,  opt_ctrl  = load_impl('optimised-implementation')

init_db_path = setup_db(init_db)
opt_db_path  = setup_db(opt_db)

# silence notifications for both
for ctrl in (init_ctrl, opt_ctrl):
    ns = ctrl.NotificationService
    for m in ('notify', 'notify_acceptance', 'notify_rejection', 'notify_revision', '_send'):
        if hasattr(ns, m):
            setattr(ns, m, lambda *a, **kw: None)
print("Done.\n")

# ─── 1. timing — submission ───────────────────────────────────────────────────

N_TIME = 400
print(f"Timing {N_TIME} submissions each …")

def time_submissions(ctrl_mod, n):
    times = []
    for i in range(n):
        data = make_data(i)
        with patch.object(ctrl_mod, 'upload_to_r2', return_value=f'/bench/{i}.pdf'):
            gc.disable()
            t0 = time.perf_counter()
            ctrl_mod.SubmissionController().submit(data)
            times.append((time.perf_counter() - t0) * 1000)
            gc.enable()
    return times

init_sub_times = time_submissions(init_ctrl, N_TIME)
opt_sub_times  = time_submissions(opt_ctrl,  N_TIME)
print(f"  Baseline  submission μ={statistics.mean(init_sub_times):.4f} ms  σ={statistics.stdev(init_sub_times):.4f}")
print(f"  Optimised submission μ={statistics.mean(opt_sub_times):.4f} ms  σ={statistics.stdev(opt_sub_times):.4f}")

# ─── 2. timing — evaluation ───────────────────────────────────────────────────

print(f"\nTiming {N_TIME} evaluation cycles each …")

def time_evaluations(ctrl_mod, db_mod, n):
    # pre-create n submissions
    sids, rids_list = [], []
    for i in range(n):
        res = submit_one(ctrl_mod, make_data(i + 50000), i)
        sid = int(res[1].split('ID: ')[1].rstrip(')'))
        sids.append(sid)
        rids_list.append(get_reviewer_ids(db_mod, sid))

    times = []
    em = ctrl_mod.EvaluationManager()
    for sid, rids in zip(sids, rids_list):
        if len(rids) < 2:
            continue
        gc.disable()
        t0 = time.perf_counter()
        em.submit_score(sid, rids[0], 8)
        em.submit_score(sid, rids[1], 7)
        times.append((time.perf_counter() - t0) * 1000)
        gc.enable()
    return times

init_eval_times = time_evaluations(init_ctrl, init_db, N_TIME)
opt_eval_times  = time_evaluations(opt_ctrl,  opt_db,  N_TIME)
print(f"  Baseline  evaluation μ={statistics.mean(init_eval_times):.4f} ms  σ={statistics.stdev(init_eval_times):.4f}")
print(f"  Optimised evaluation μ={statistics.mean(opt_eval_times):.4f} ms  σ={statistics.stdev(opt_eval_times):.4f}")

# ─── 3. domain method call counts (instrumented) ──────────────────────────────

print("\nCounting domain method calls …")

INIT_SUBMISSION_METHODS = [
    'validate_format', 'save_submission', 'fetch_reviewers',
    'filter_conflicts', 'check_workload', 'get_available_reviewers',
    'save_review_assignment', 'start_evaluation', 'assign_review',
]
OPT_SUBMISSION_METHODS = [
    'validate_format', 'save_submission', 'fetch_reviewers',
    '_filter_conflicts', '_check_workload', 'assign_reviewers', 'save_assignments',
]

INIT_EVAL_METHODS = [
    'submit_score', 'save_score', 'get_scores', 'calculate_average',
    'check_consensus', 'apply_rules', 'update_status',
    'notify_acceptance', 'notify_rejection', 'notify_revision',
]
OPT_EVAL_METHODS = [
    'submit_score', 'save_score', 'get_scores', 'evaluate',
    'update_status', 'notify',
]

def count_domain_calls(ctrl_mod, db_mod, submission_methods, eval_methods):
    # ── submission ──
    sc = ctrl_mod.SubmissionController()
    v_counts, v_orig = instrument(sc.validator, ['validate_format'])
    rm_counts, rm_orig = instrument(sc.reviewer_manager, [m for m in submission_methods
                                                           if m not in ('validate_format', 'save_submission',
                                                                        'fetch_reviewers', 'save_review_assignment',
                                                                        'save_assignments')])
    db_sub_counts, db_sub_orig = instrument(db_mod.Database(), ['save_submission', 'fetch_reviewers',
                                                                  'save_review_assignment', 'save_assignments'])
    # patch _db in ctrl_mod
    old_db = ctrl_mod._db
    ctrl_mod._db = db_mod.Database()
    sub_db_counts, sub_db_orig = instrument(ctrl_mod._db, ['save_submission', 'fetch_reviewers',
                                                            'save_review_assignment', 'save_assignments'])

    # Reviewer (baseline only)
    if hasattr(ctrl_mod, 'Reviewer'):
        orig_reviewer_init = ctrl_mod.Reviewer.__init__
        reviewer_assign_count = [0]
        def counted_assign(self, sid):
            reviewer_assign_count[0] += 1
            db_mod.Database().save_review_assignment(sid, self.reviewer_id)
        ctrl_mod.Reviewer.assign_review = counted_assign

    with patch.object(ctrl_mod, 'upload_to_r2', return_value='/bench/count.pdf'):
        ctrl_mod._db = sub_db_counts if False else ctrl_mod._db  # already patched
        result = sc.submit(make_data(999991))
    sid = int(result[1].split('ID: ')[1].rstrip(')'))
    rids = get_reviewer_ids(db_mod, sid)

    sub_total = (v_counts.get('validate_format', 0) +
                 sum(sub_db_counts.values()) +
                 sum(rm_counts.values()) +
                 (reviewer_assign_count[0] if hasattr(ctrl_mod, 'Reviewer') else 0))

    # ── evaluation ──
    ctrl_mod._db = old_db  # restore
    em = ctrl_mod.EvaluationManager()
    em_counts, em_orig = instrument(em, eval_methods)
    if len(rids) >= 2:
        em.submit_score(sid, rids[0], 8)
        em.submit_score(sid, rids[1], 7)
    restore(em, em_orig)

    return sub_total, sum(em_counts.values()), sub_db_counts, em_counts


# Simpler, direct approach: use sys.settrace for total calls
def count_total_calls_submission(ctrl_mod, db_mod):
    counter = TraceCounter()
    with patch.object(ctrl_mod, 'upload_to_r2', return_value='/bench/tc_sub.pdf'):
        with counter:
            ctrl_mod.SubmissionController().submit(make_data(888881))
    return counter.n

def count_total_calls_evaluation(ctrl_mod, db_mod):
    res = submit_one(ctrl_mod, make_data(888882), 888882)
    sid = int(res[1].split('ID: ')[1].rstrip(')'))
    rids = get_reviewer_ids(db_mod, sid)
    if len(rids) < 2:
        return 0
    em = ctrl_mod.EvaluationManager()
    counter = TraceCounter()
    with counter:
        em.submit_score(sid, rids[0], 8)
        em.submit_score(sid, rids[1], 7)
    return counter.n

init_sub_calls  = count_total_calls_submission(init_ctrl, init_db)
opt_sub_calls   = count_total_calls_submission(opt_ctrl,  opt_db)
init_eval_calls = count_total_calls_evaluation(init_ctrl, init_db)
opt_eval_calls  = count_total_calls_evaluation(opt_ctrl,  opt_db)
print(f"  Total function calls — Submission:  Baseline={init_sub_calls}  Optimised={opt_sub_calls}")
print(f"  Total function calls — Evaluation:  Baseline={init_eval_calls}  Optimised={opt_eval_calls}")

# ─── 4. DB connection counts ──────────────────────────────────────────────────

print("\nCounting DB connections …")

def count_db_connections(ctrl_mod, db_mod, op):
    calls = [0]
    orig = db_mod.get_db_connection
    def wrapper():
        calls[0] += 1
        return orig()
    db_mod.get_db_connection = wrapper
    op()
    db_mod.get_db_connection = orig
    return calls[0]

init_sub_db = count_db_connections(init_ctrl, init_db,
    lambda: submit_one(init_ctrl, make_data(777771), 777771))
opt_sub_db  = count_db_connections(opt_ctrl, opt_db,
    lambda: submit_one(opt_ctrl, make_data(777772), 777772))

def make_eval_op(ctrl_mod, db_mod, idx):
    res  = submit_one(ctrl_mod, make_data(idx), idx)
    sid  = int(res[1].split('ID: ')[1].rstrip(')'))
    rids = get_reviewer_ids(db_mod, sid)
    em   = ctrl_mod.EvaluationManager()
    def op():
        if len(rids) >= 2:
            em.submit_score(sid, rids[0], 8)
            em.submit_score(sid, rids[1], 7)
    return op

init_eval_op = make_eval_op(init_ctrl, init_db, 777773)
opt_eval_op  = make_eval_op(opt_ctrl,  opt_db,  777774)
init_eval_db = count_db_connections(init_ctrl, init_db, init_eval_op)
opt_eval_db  = count_db_connections(opt_ctrl,  opt_db,  opt_eval_op)
print(f"  DB connections — Submission:  Baseline={init_sub_db}  Optimised={opt_sub_db}")
print(f"  DB connections — Evaluation:  Baseline={init_eval_db}  Optimised={opt_eval_db}")

# ─── 5. static code metrics ───────────────────────────────────────────────────

print("\nParsing static metrics …")

def parse_metrics(filepath):
    with open(filepath) as f:
        source = f.read()
    tree = ast.parse(source)
    # total non-blank, non-comment lines
    loc = sum(1 for l in source.splitlines() if l.strip() and not l.strip().startswith('#'))
    classes = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        methods = [n for n in ast.walk(node) if isinstance(n, ast.FunctionDef)]
        pub     = [m for m in methods if not m.name.startswith('_')]
        # cyclomatic complexity per method
        cc = 0
        method_locs = []
        for m in methods:
            c = 1
            for child in ast.walk(m):
                if isinstance(child, (ast.If, ast.While, ast.For,
                                       ast.ExceptHandler, ast.With)):
                    c += 1
                elif isinstance(child, ast.BoolOp):
                    c += len(child.values) - 1
            cc += c
            method_locs.append(m.end_lineno - m.lineno + 1)
        classes[node.name] = {
            'loc':            node.end_lineno - node.lineno + 1,
            'methods':        len(methods),
            'public_methods': len(pub),
            'complexity':     cc,
            'avg_method_loc': round(statistics.mean(method_locs), 1) if method_locs else 0,
        }
    return loc, classes

init_loc, init_classes = parse_metrics(os.path.join(ROOT, 'initial-implementation',  'controllers.py'))
opt_loc,  opt_classes  = parse_metrics(os.path.join(ROOT, 'optimised-implementation', 'controllers.py'))

ALL_CLASSES = ['Validator', 'ReviewerManager', 'Reviewer',
               'NotificationService', 'EvaluationManager', 'SubmissionController']
print(f"  Total LOC (controllers.py): Baseline={init_loc}  Optimised={opt_loc}")
for cls in ALL_CLASSES:
    i = init_classes.get(cls, {})
    o = opt_classes.get(cls, {})
    print(f"  {cls:<25} LOC: {i.get('loc','—'):>4} → {o.get('loc','REMOVED'):>7}   "
          f"pub_methods: {i.get('public_methods','—')} → {o.get('public_methods','—')}   "
          f"CC: {i.get('complexity','—')} → {o.get('complexity','—')}")

# ─── 6. generate graphs ───────────────────────────────────────────────────────

print("\nGenerating graphs …")
WIDTH = 0.35

# ── Figure 1: Execution time box plots ────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle('Figure 1 — Execution Time Distribution (ms)\n'
             f'n={N_TIME} runs per implementation per operation', fontweight='bold')

for ax, (init_t, opt_t, title) in zip(axes, [
    (init_sub_times, opt_sub_times, 'Submission Flow'),
    (init_eval_times, opt_eval_times, 'Score Submission + Evaluation'),
]):
    bp = ax.boxplot([init_t, opt_t], patch_artist=True, widths=0.45,
                    medianprops={'color': 'black', 'linewidth': 2.5},
                    flierprops={'marker': '.', 'markersize': 3, 'alpha': 0.4})
    for box, col in zip(bp['boxes'], [BASELINE_COL, OPT_COL]):
        box.set_facecolor(col); box.set_alpha(0.75)
    for whisker in bp['whiskers']: whisker.set_linestyle('--')
    ax.set_xticklabels([BASELINE_LBL, OPT_LBL], fontsize=12)
    ax.set_ylabel('Time (ms)')
    ax.set_title(title)
    for i, times in enumerate([init_t, opt_t], 1):
        m = statistics.mean(times)
        ax.text(i + 0.28, m, f'μ={m:.4f}', va='center', fontsize=8.5, color='#2c3e50')
    pct = (statistics.mean(opt_t) - statistics.mean(init_t)) / statistics.mean(init_t) * 100
    ax.text(0.98, 0.97, f'Δμ = {pct:+.1f}%', transform=ax.transAxes,
            ha='right', va='top', fontsize=10,
            color=OPT_COL if pct < 0 else BASELINE_COL, fontweight='bold')

plt.tight_layout()
plt.savefig(os.path.join(GRAPHS_DIR, 'fig1_execution_time.png'), bbox_inches='tight')
plt.close()
print("  fig1_execution_time.png")

# ── Figure 2: Mean execution time with std-dev error bars ─────────────────────
fig, axes = plt.subplots(1, 2, figsize=(11, 5))
fig.suptitle('Figure 2 — Mean Execution Time ± 1 SD (ms)', fontweight='bold')

for ax, (init_t, opt_t, title) in zip(axes, [
    (init_sub_times, opt_sub_times, 'Submission Flow'),
    (init_eval_times, opt_eval_times, 'Score Submission + Evaluation'),
]):
    means = [statistics.mean(init_t), statistics.mean(opt_t)]
    stds  = [statistics.stdev(init_t), statistics.stdev(opt_t)]
    bars  = ax.bar([BASELINE_LBL, OPT_LBL], means, yerr=stds, capsize=7,
                   color=[BASELINE_COL, OPT_COL], alpha=0.8, width=0.45,
                   error_kw={'linewidth': 2})
    for bar, m in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(stds)*0.12,
                f'{m:.4f}', ha='center', va='bottom', fontsize=9, fontweight='bold')
    pct = (means[1] - means[0]) / means[0] * 100
    ax.set_title(f'{title}\n({pct:+.1f}% mean change)')
    ax.set_ylabel('Time (ms)')
    ax.set_ylim(0, max(means) + max(stds) * 2.5)

plt.tight_layout()
plt.savefig(os.path.join(GRAPHS_DIR, 'fig2_mean_time.png'), bbox_inches='tight')
plt.close()
print("  fig2_mean_time.png")

# ── Figure 3: Total function call count ───────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 5))
fig.suptitle('Figure 3 — Total Python Function Calls per Operation', fontweight='bold')

ops        = ['Submission', 'Evaluation\n(2 scores + trigger)']
init_calls = [init_sub_calls, init_eval_calls]
opt_calls  = [opt_sub_calls,  opt_eval_calls]
x = np.arange(len(ops))

b1 = ax.bar(x - WIDTH/2, init_calls, WIDTH, label=BASELINE_LBL, color=BASELINE_COL, alpha=0.8)
b2 = ax.bar(x + WIDTH/2, opt_calls,  WIDTH, label=OPT_LBL,      color=OPT_COL,      alpha=0.8)
for b in list(b1) + list(b2):
    ax.text(b.get_x() + b.get_width()/2, b.get_height() + max(init_calls)*0.01,
            f'{int(b.get_height())}', ha='center', va='bottom', fontsize=9, fontweight='bold')
for i, (ic, oc) in enumerate(zip(init_calls, opt_calls)):
    pct = (ic - oc) / ic * 100
    ax.annotate(f'↓{pct:.0f}%', xy=(i, max(ic, oc) * 1.08),
                ha='center', color='navy', fontsize=11, fontweight='bold')

ax.set_xticks(x); ax.set_xticklabels(ops)
ax.set_ylabel('Function Calls')
ax.legend()
ax.set_ylim(0, max(init_calls) * 1.25)
plt.tight_layout()
plt.savefig(os.path.join(GRAPHS_DIR, 'fig3_function_calls.png'), bbox_inches='tight')
plt.close()
print("  fig3_function_calls.png")

# ── Figure 4: DB connection counts ────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 5))
fig.suptitle('Figure 4 — Database Connection Open/Close Cycles per Operation', fontweight='bold')

ops_db        = ['Submission\nFlow', 'Evaluation Flow\n(2 scores)']
init_db_list  = [init_sub_db, init_eval_db]
opt_db_list   = [opt_sub_db,  opt_eval_db]
x = np.arange(len(ops_db))

b1 = ax.bar(x - WIDTH/2, init_db_list, WIDTH, label=BASELINE_LBL, color=BASELINE_COL, alpha=0.8)
b2 = ax.bar(x + WIDTH/2, opt_db_list,  WIDTH, label=OPT_LBL,      color=OPT_COL,      alpha=0.8)
for b in list(b1) + list(b2):
    ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.06,
            str(int(b.get_height())), ha='center', va='bottom', fontsize=11, fontweight='bold')
for i, (ic, oc) in enumerate(zip(init_db_list, opt_db_list)):
    if ic > oc:
        pct = (ic - oc) / ic * 100
        ax.annotate(f'↓{pct:.0f}%', xy=(i, ic + 0.4),
                    ha='center', color='navy', fontsize=11, fontweight='bold')

ax.set_xticks(x); ax.set_xticklabels(ops_db)
ax.set_ylabel('DB Connection Cycles')
ax.legend()
ax.set_ylim(0, max(init_db_list) * 1.35)
plt.tight_layout()
plt.savefig(os.path.join(GRAPHS_DIR, 'fig4_db_connections.png'), bbox_inches='tight')
plt.close()
print("  fig4_db_connections.png")

# ── Figure 5: Lines of code per class ─────────────────────────────────────────
fig, ax = plt.subplots(figsize=(12, 5))
fig.suptitle('Figure 5 — Lines of Code per Class (controllers.py)', fontweight='bold')

present = [c for c in ALL_CLASSES if c in init_classes]
x = np.arange(len(present))
i_locs = [init_classes[c]['loc'] for c in present]
o_locs = [opt_classes[c]['loc'] if c in opt_classes else 0 for c in present]

b1 = ax.bar(x - WIDTH/2, i_locs, WIDTH, label=BASELINE_LBL, color=BASELINE_COL, alpha=0.8)
b2 = ax.bar(x + WIDTH/2, o_locs, WIDTH, label=OPT_LBL,      color=OPT_COL,      alpha=0.8)
for b, v in zip(list(b1) + list(b2), i_locs + o_locs):
    if v > 0:
        ax.text(b.get_x() + b.get_width()/2, v + 0.3, str(v),
                ha='center', va='bottom', fontsize=8.5)
    else:
        ax.text(b.get_x() + b.get_width()/2, 1, 'removed',
                ha='center', va='bottom', fontsize=7.5, color='grey', style='italic')

ax.set_xticks(x); ax.set_xticklabels(present, rotation=12, ha='right')
ax.set_ylabel('Lines of Code')
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(GRAPHS_DIR, 'fig5_loc_per_class.png'), bbox_inches='tight')
plt.close()
print("  fig5_loc_per_class.png")

# ── Figure 6: Cyclomatic complexity ───────────────────────────────────────────
fig, ax = plt.subplots(figsize=(12, 5))
fig.suptitle('Figure 6 — Cumulative Cyclomatic Complexity per Class', fontweight='bold')

i_cc = [init_classes[c]['complexity'] for c in present]
o_cc = [opt_classes[c]['complexity'] if c in opt_classes else 0 for c in present]

b1 = ax.bar(x - WIDTH/2, i_cc, WIDTH, label=BASELINE_LBL, color=BASELINE_COL, alpha=0.8)
b2 = ax.bar(x + WIDTH/2, o_cc, WIDTH, label=OPT_LBL,      color=OPT_COL,      alpha=0.8)
for b, v in zip(list(b1) + list(b2), i_cc + o_cc):
    if v > 0:
        ax.text(b.get_x() + b.get_width()/2, v + 0.05, str(v),
                ha='center', va='bottom', fontsize=8.5)
    else:
        ax.text(b.get_x() + b.get_width()/2, 0.3, 'removed',
                ha='center', va='bottom', fontsize=7.5, color='grey', style='italic')

ax.axhline(y=10, color='orange', linestyle='--', alpha=0.7, label='High complexity threshold (10)')
ax.set_xticks(x); ax.set_xticklabels(present, rotation=12, ha='right')
ax.set_ylabel('Cumulative Cyclomatic Complexity')
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(GRAPHS_DIR, 'fig6_complexity.png'), bbox_inches='tight')
plt.close()
print("  fig6_complexity.png")

# ── Figure 7: Public methods per class ────────────────────────────────────────
fig, ax = plt.subplots(figsize=(12, 5))
fig.suptitle('Figure 7 — Public Methods per Class', fontweight='bold')

i_pub = [init_classes[c]['public_methods'] for c in present]
o_pub = [opt_classes[c]['public_methods'] if c in opt_classes else 0 for c in present]

b1 = ax.bar(x - WIDTH/2, i_pub, WIDTH, label=BASELINE_LBL, color=BASELINE_COL, alpha=0.8)
b2 = ax.bar(x + WIDTH/2, o_pub, WIDTH, label=OPT_LBL,      color=OPT_COL,      alpha=0.8)
for b, v in zip(list(b1) + list(b2), i_pub + o_pub):
    ax.text(b.get_x() + b.get_width()/2, v + 0.03, str(v),
            ha='center', va='bottom', fontsize=9, fontweight='bold')

ax.set_xticks(x); ax.set_xticklabels(present, rotation=12, ha='right')
ax.set_ylabel('Number of Public Methods')
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(GRAPHS_DIR, 'fig7_public_methods.png'), bbox_inches='tight')
plt.close()
print("  fig7_public_methods.png")

# ── Figure 8: Summary horizontal improvement chart ────────────────────────────
def pct_change(b, o):
    return (b - o) / b * 100 if b else 0

ns_pub_i = init_classes.get('NotificationService', {}).get('public_methods', 3)
ns_pub_o = opt_classes.get('NotificationService',  {}).get('public_methods', 1)
em_pub_i = init_classes.get('EvaluationManager',   {}).get('public_methods', 4)
em_pub_o = opt_classes.get('EvaluationManager',    {}).get('public_methods', 2)
sc_pub_i = init_classes.get('SubmissionController',{}).get('public_methods', 1)
rm_i     = init_classes.get('ReviewerManager',     {}).get('public_methods', 3)
rm_o     = opt_classes.get('ReviewerManager',      {}).get('public_methods', 1)

labels = [
    'Function calls — Submission',
    'Function calls — Evaluation',
    'DB connections — Submission',
    'DB connections — Evaluation',
    'controllers.py total LOC',
    'NotificationService public methods',
    'EvaluationManager public methods',
    'ReviewerManager public methods',
    'Number of classes (controllers.py)',
]
reductions = [
    pct_change(init_sub_calls,  opt_sub_calls),
    pct_change(init_eval_calls, opt_eval_calls),
    pct_change(init_sub_db,  opt_sub_db),
    pct_change(init_eval_db, opt_eval_db),
    pct_change(init_loc,  opt_loc),
    pct_change(ns_pub_i, ns_pub_o),
    pct_change(em_pub_i, em_pub_o),
    pct_change(rm_i, rm_o),
    pct_change(len(init_classes), len(opt_classes)),
]

fig, ax = plt.subplots(figsize=(12, 7))
fig.suptitle('Figure 8 — Summary: % Reduction from Baseline to Optimised\n'
             '(positive = improvement; negative = increase)', fontweight='bold')

colors = [OPT_COL if r >= 0 else BASELINE_COL for r in reductions]
bars   = ax.barh(labels, reductions, color=colors, alpha=0.82, height=0.55)
for bar, val in zip(bars, reductions):
    xoff = 0.8 if val >= 0 else -0.8
    ha   = 'left' if val >= 0 else 'right'
    ax.text(val + xoff, bar.get_y() + bar.get_height()/2,
            f'{val:+.1f}%', va='center', ha=ha, fontsize=9.5, fontweight='bold')

ax.axvline(x=0, color='#2c3e50', linewidth=1)
ax.set_xlabel('% Change (positive = reduction / improvement)')
ax.set_xlim(-10, max(reductions) * 1.18 + 5)
legend_patches = [
    mpatches.Patch(color=OPT_COL,      alpha=0.82, label='Improvement (reduced)'),
    mpatches.Patch(color=BASELINE_COL, alpha=0.82, label='Increase'),
]
ax.legend(handles=legend_patches, loc='lower right')
plt.tight_layout()
plt.savefig(os.path.join(GRAPHS_DIR, 'fig8_summary.png'), bbox_inches='tight')
plt.close()
print("  fig8_summary.png")

# ─── 7. print final summary ───────────────────────────────────────────────────

print("\n" + "=" * 65)
print("BENCHMARK SUMMARY")
print("=" * 65)
print(f"{'Metric':<45} {'Baseline':>8} {'Optimised':>9} {'Change':>9}")
print("-" * 65)

rows = [
    ("Submission: total function calls",     init_sub_calls,  opt_sub_calls),
    ("Evaluation: total function calls",     init_eval_calls, opt_eval_calls),
    ("Submission: DB connections",           init_sub_db,     opt_sub_db),
    ("Evaluation: DB connections (2 scores)",init_eval_db,    opt_eval_db),
    ("controllers.py: total LOC",            init_loc,        opt_loc),
    ("controllers.py: number of classes",    len(init_classes), len(opt_classes)),
]
for label, b, o in rows:
    pct = pct_change(b, o)
    print(f"{label:<45} {b:>8} {o:>9} {pct:>+8.1f}%")

print()
for label, init_t, opt_t in [
    ("Submission mean time (ms)",  init_sub_times,  opt_sub_times),
    ("Evaluation mean time (ms)",  init_eval_times, opt_eval_times),
]:
    bm, om = statistics.mean(init_t), statistics.mean(opt_t)
    bs, opt_sd = statistics.stdev(init_t), statistics.stdev(opt_t)
    pct = pct_change(bm, om)
    print(f"{label:<45} {bm:>8.4f} {om:>9.4f} {pct:>+8.1f}%")
    print(f"  {'std dev':<43} {bs:>8.4f} {opt_sd:>9.4f}")
    print(f"  {'median':<43} {statistics.median(init_t):>8.4f} {statistics.median(opt_t):>9.4f}")
    print(f"  {'p95':<43} {np.percentile(init_t,95):>8.4f} {np.percentile(opt_t,95):>9.4f}")
    print()

print(f"\nClass-level static metrics:")
print(f"{'Class':<25} {'Baseline LOC':>12} {'Opt LOC':>8} {'B pub mth':>10} {'O pub mth':>10} {'B CC':>6} {'O CC':>6}")
print("-" * 80)
for cls in ALL_CLASSES:
    i = init_classes.get(cls, {})
    o = opt_classes.get(cls, {})
    print(f"{cls:<25} {i.get('loc','—'):>12} {o.get('loc','—'):>8} "
          f"{i.get('public_methods','—'):>10} {o.get('public_methods','—'):>10} "
          f"{i.get('complexity','—'):>6} {o.get('complexity','—'):>6}")

# cleanup temp dbs
os.unlink(init_db_path)
os.unlink(opt_db_path)

print(f"\nAll graphs → {GRAPHS_DIR}/")
print("Benchmark complete.")
