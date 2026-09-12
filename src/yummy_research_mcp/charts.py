"""Render the immutable snapshot; never fetch different data for the picture."""
from pathlib import Path
import os

def render(snapshot, output):
    os.environ.setdefault('MPLCONFIGDIR','/tmp/yummy-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    groups=[('US Treasury yields (%)',['us3y','us10y','us30y']),('WTI spot (USD/barrel)',['wti'])]
    items={r['metric_id']:r for r in snapshot['items']}
    fig,axes=plt.subplots(2,1,figsize=(9,7),layout='constrained')
    from datetime import datetime
    for ax,(title,ids) in zip(axes,groups):
        drawn=False
        for metric in ids:
            row=items.get(metric)
            if not row:continue
            history=row['history']
            ax.plot([datetime.fromisoformat(v['date']) for v in history],[v['value'] for v in history],label=metric.upper(),linewidth=1.7)
            drawn=True
        ax.set_title(title,loc='left');ax.grid(alpha=.2)
        if drawn:ax.legend();ax.tick_params(axis='x',rotation=15)
        else:ax.text(.5,.5,'Data unavailable',ha='center',transform=ax.transAxes)
    fig.suptitle('Yummy | Last 60 observations\nAs of '+snapshot['as_of'][:19]+' UTC',fontsize=12)
    fig.text(.01,.002,'Source: FRED | Daily observations; not real-time quotes. Snapshot '+snapshot['snapshot_id'],fontsize=7)
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(output,dpi=140);plt.close(fig)
    return {'status':'ok','path':str(output.resolve()),'snapshot_id':snapshot['snapshot_id']}
