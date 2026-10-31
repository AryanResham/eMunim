"""Small, explicit metric primitives. Undefined denominators remain None."""
import math


def wilson(successes, count):
    if not count:
        return None
    z=1.959963984540054
    p=successes/count
    denominator=1+z*z/count
    center=(p+z*z/(2*count))/denominator
    radius=z*math.sqrt(p*(1-p)/count+z*z/(4*count*count))/denominator
    return [max(0,center-radius),min(1,center+radius)]


def calibration(observations):
    if not observations:
        return {"samples":0,"brier_score":None,"ece_10_bins":None,"correctness_auroc":None,"bins":[]}
    if any(not math.isfinite(p) or not 0<=p<=1 or y not in (0,1) for p,y in observations):
        raise ValueError("Invalid confidence/calibration observations")
    bins=[]
    for i in range(10):
        group=[(p,y) for p,y in observations if min(int(p*10),9)==i]
        bins.append({"lower":i/10,"upper":(i+1)/10,"count":len(group),
                     "mean_confidence":sum(p for p,_ in group)/len(group) if group else None,
                     "accuracy":sum(y for _,y in group)/len(group) if group else None})
    positives=sum(y for _,y in observations);negatives=len(observations)-positives
    ranks=0.;ordered=sorted(observations);i=0
    while i<len(ordered):
        j=i+1
        while j<len(ordered) and ordered[j][0]==ordered[i][0]:
            j+=1
        ranks+=sum(y for _,y in ordered[i:j])*((i+1+j)/2)
        i=j
    return {"samples":len(observations),"brier_score":sum((p-y)**2 for p,y in observations)/len(observations),
            "ece_10_bins":sum(b["count"]*abs(b["mean_confidence"]-b["accuracy"]) for b in bins if b["count"])/len(observations),
            "correctness_auroc":(ranks-positives*(positives+1)/2)/(positives*negatives) if positives and negatives else None,
            "bins":bins,"scope":"Populated LayoutLM fields only; softmax is not assumed calibrated"}


def edit_distance(reference,predicted):
    previous=list(range(len(predicted)+1))
    for i,left in enumerate(reference,1):
        current=[i]
        for j,right in enumerate(predicted,1):
            current.append(min(current[-1]+1,previous[j]+1,previous[j-1]+(left!=right)))
        previous=current
    return previous[-1]
