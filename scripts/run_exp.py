import asyncio 
import apeiron.utils as U
from apeiron.system import build_system

async def main(): 
    exp_name = 'exp002'
    cfg_name = 'default'
    cfg_dir = U.pjoin(U.PROJECT_ROOT, 'configs', f'{cfg_name}.yaml')
    assert U.pexists(cfg_dir), f"Config file not found: {cfg_dir}"
    U.cprint(f'Running on configuration: {cfg_dir}','g')
    config = U.load_config(cfg_dir)

    system = build_system(config, exp_name=exp_name)
    await system.xbuild() 


if __name__ == "__main__":
    asyncio.run(main())
    
