"""On-policy clipped PPO with a projected SLA Lagrange multiplier (CPU)."""
import csv
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

import numpy as np
import torch
from torch.distributions import Categorical
from backend.models import ActorCritic, WEIGHTS, dispatch_bias
from backend.planner import DEFAULT
from backend.simulation import ComputeEnv
from backend.world import SCENARIOS


def distribution(logits, mask):
    return Categorical(logits=logits.masked_fill(~mask,-1e8))


def train():
    torch.manual_seed(270)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    model = ActorCritic()
    opt = torch.optim.Adam(model.parameters(),lr=.002)
    multiplier = 1.
    log = []
    done = True
    episode = -1
    for update in range(160):
        if done:
            episode += 1
            env = ComputeEnv(hours=24,scenario=SCENARIOS[episode%4],macro=episode%8<4,policy=model)
            obs,info = env.reset(seed=5000+episode)
        states,masks,actions,old_logp,values,rewards,costs = [],[],[],[],[],[],[]
        for _ in range(384):
            s = torch.from_numpy(obs)
            mask = torch.from_numpy(info["action_mask"])
            if not mask.any():
                mask[:] = True
            with torch.no_grad():
                dist = distribution(model(s)+dispatch_bias(s,DEFAULT),mask)
                action = dist.sample()
                prob = dist.log_prob(action)
                v = model.critic(s)
            obs,reward,done,_,info = env.step(action.item())
            states.append(s)
            masks.append(mask)
            actions.append(action)
            old_logp.append(prob)
            values.append(v.item())
            rewards.append(reward)
            costs.append(info["cost"])
            if done:
                break
        with torch.no_grad():
            bootstrap = 0. if done else model.critic(torch.from_numpy(obs)).item()
        adjusted = np.asarray(rewards)-multiplier*np.asarray(costs)
        adv = np.empty(len(values),dtype=np.float32)
        tail = 0.
        for i in reversed(range(len(values))):
            delta = adjusted[i]+.97*bootstrap-values[i]
            tail = delta+.97*.92*tail
            adv[i],bootstrap = tail,values[i]
        returns = torch.tensor(adv+np.asarray(values,dtype=np.float32))
        advantages = torch.from_numpy((adv-adv.mean())/(adv.std()+1e-6))
        data = list(map(torch.stack,(states,masks,actions,old_logp)))
        for _ in range(4):
            for idx in torch.randperm(len(adv)).split(96):
                s,mask,a,old = (v[idx] for v in data)
                dist = distribution(model(s)+dispatch_bias(s,DEFAULT),mask)
                ratio = torch.exp(dist.log_prob(a)-old)
                gain = torch.minimum(ratio*advantages[idx],ratio.clamp(.8,1.2)*advantages[idx])
                loss = (-gain.mean()+.25*torch.nn.functional.smooth_l1_loss(
                        model.critic(s),returns[idx])-.002*dist.entropy().mean())
                opt.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(),.8)
                opt.step()
        rate = float(np.mean(costs))
        multiplier = max(0.,multiplier+4*(rate-.005))
        log.append(dict(update=update+1,seed=5000+episode,steps=len(adv),
                        mean_reward=float(np.mean(rewards)),violation_rate=rate,
                        lagrange_multiplier=multiplier))
    torch.save(model.state_dict(),WEIGHTS/"policy.pt")
    with (WEIGHTS/"ppo_training.csv").open("w",newline="") as f:
        out = csv.DictWriter(f,log[0].keys(),lineterminator="\n")
        out.writeheader()
        out.writerows(log)
    torch.onnx.export(model.eval(),torch.zeros(1,96,15),str(WEIGHTS/"policy.onnx"),
                      input_names=["candidates"],output_names=["logits"],
                      dynamic_axes={"candidates":{0:"batch"},"logits":{0:"batch"}},
                      opset_version=17,dynamo=False)
    print("First/last ten rewards",*[np.mean([r['mean_reward'] for r in block])
          for block in (log[:10],log[-10:])])


if __name__=="__main__":
    train()
