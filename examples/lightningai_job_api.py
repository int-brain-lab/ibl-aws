from pathlib import Path
import dotenv
from lightning_sdk import Machine, Studio
import iblaws

dotenv.load_dotenv(
    dotenv_path=Path(iblaws.__file__).parents[2].joinpath('.env'))  # Load environment variables from .env file

s = Studio(name='muddy-emerald-fbcv 2xt1', org='IBL', teamspace='Spike Sorting')
pid = '6e1379e8-3af0-4fc5-8ba8-37d3bb02226b'  # 7000+
cmd, jobname = (f'python  spike_sort.py {pid}', pid)
s.run_job(command=cmd, machine=Machine.L4, name=jobname)
