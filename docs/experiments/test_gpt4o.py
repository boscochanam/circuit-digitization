#!/usr/bin/env python3
"""Test GPT-4o-mini vision rating vs actual F1 on failing images."""
import os, base64, math, requests, cv2, numpy as np
from pathlib import Path

env_path=Path.home()/".hermes"/".env"
with open(env_path) as f:
    for line in f:
        if line.startswith("OPENROUTER_API_KEY="):
            AK=line.strip().split("=",1)[1];break

GT_DIR=Path("/home/claw/workspace/ground_truth/labels_few_annot/labels/train/manually_verified_no_background_data/images")
IMAGES_DIR=Path("/home/claw/workspace/ground_truth/labels_few_annot/images")

def load_gt(path,w,h):
    lines=[]
    with open(path) as f:
        for line in f:
            p=line.strip().split()
            if len(p)<9:continue
            try:
                c=[float(x) for x in p[1:9]]
                poly=np.array([[int(c[i]*w),int(c[i+1]*h)] for i in range(0,8,2)],dtype=np.int32)
                edges=[(i,(i+1)%4) for i in range(4)]
                el=sorted([(np.linalg.norm(poly[a]-poly[b]),a,b) for a,b in edges])
                m1=(poly[el[0][1]]+poly[el[0][2]])/2;m2=(poly[el[1][1]]+poly[el[1][2]])/2
                lines.append(((int(m1[0]),int(m1[1])),(int(m2[0]),int(m2[1]))))
            except:pass
    return lines

def ptd(p,a,b):
    ax,ay=a;bx,by=b;px,py=p
    abx,aby=bx-ax,by-ay;t=((px-ax)*abx+(py-ay)*aby)/max(abx*abx+aby*aby,1e-8)
    t=max(0,min(1,t));return math.hypot(px-(ax+t*abx),py-(ay+t*aby))

def pipe(gray,k=0.3,w=51,cks=3,cma=20,da=10,dd=18,ma_=10,mg_=30,ml=10):
    mean=cv2.boxFilter(gray.astype(np.float32),-1,(w,w),normalize=True)
    sqr=cv2.boxFilter((gray.astype(np.float32))**2,-1,(w,w),normalize=True)
    std=np.sqrt(np.maximum(sqr-mean**2,0))
    bw=(gray>mean*(1+k*(std/128-1))).astype(np.uint8)*255;bw=cv2.bitwise_not(bw)
    k_=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(cks,cks));cl=cv2.morphologyEx(bw,cv2.MORPH_CLOSE,k_)
    nlab,labels,stats,_=cv2.connectedComponentsWithStats(cl)
    lines=[]
    for i in range(1,nlab):
        if stats[i,cv2.CC_STAT_AREA]<cma:continue
        mask=(labels==i).astype(np.uint8)*255
        cnts,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:continue
        cnt=max(cnts,key=cv2.contourArea)
        pts=[tuple(cnt[cnt[:,:,0].argmin()][0]),tuple(cnt[cnt[:,:,0].argmax()][0]),
             tuple(cnt[cnt[:,:,1].argmin()][0]),tuple(cnt[cnt[:,:,1].argmax()][0])]
        bd_,bp_=-1,None
        for a in range(4):
            for b in range(a+1,4):
                d=(pts[a][0]-pts[b][0])**2+(pts[a][1]-pts[b][1])**2
                if d>bd_:bd_,bp_=d,(pts[a],pts[b])
        if bp_:lines.append(bp_)
    if da>0:
        at=math.radians(da);kep=list(lines);ch=True
        while ch:
            ch=False;i=0
            while i<len(kep):
                j=i+1
                while j<len(kep):
                    p1,p2=kep[i];q1,q2=kep[j]
                    dx1,dy1=p2[0]-p1[0],p2[1]-p1[1];dx2,dy2=q2[0]-q1[0],q2[1]-q1[1]
                    l1,l2=math.hypot(dx1,dy1),math.hypot(dx2,dy2)
                    if l1<1 or l2<1:j+=1;continue
                    ab=math.acos(max(-1,min(1,(dx1*dx2+dy1*dy2)/(l1*l2))))
                    if ab>at:j+=1;continue
                    longer=kep[i]if l1>=l2 else kep[j];shorter=kep[j]if l1>=l2 else kep[i]
                    if ptd(shorter[0],longer[0],longer[1])<=dd and ptd(shorter[1],longer[0],longer[1])<=dd:
                        kep.pop(j);ch=True
                    else:j+=1
                i+=1
        lines=kep
    lines=[l for l in lines if math.hypot(l[0][0]-l[1][0],l[0][1]-l[1][1])>=ml]
    r=list(lines);ch=True
    while ch:
        ch=False;i=0
        while i<len(r):
            j=i+1
            while j<len(r):
                p1,p2=r[i];q1,q2=r[j]
                dx1,dy1=p2[0]-p1[0],p2[1]-p1[1];dx2,dy2=q2[0]-q1[0],q2[1]-q1[1]
                l1,l2=math.hypot(dx1,dy1),math.hypot(dx2,dy2)
                if l1<1 or l2<1:j+=1;continue
                a=math.degrees(math.acos(max(-1,min(1,(dx1*dx2+dy1*dy2)/(l1*l2)))))
                if a>ma_:j+=1;continue
                mg=min(math.hypot(p1[0]-q1[0],p1[1]-q1[1]),math.hypot(p2[0]-q1[0],p2[1]-q1[1]),
                       math.hypot(p1[0]-q2[0],p1[1]-q2[1]),math.hypot(p2[0]-q2[0],p2[1]-q2[1]))
                if mg<=mg_:
                    ap=[p1,p2,q1,q2];md=-1;bp=(p1,q1)
                    for a2 in range(4):
                        for b2 in range(a2+1,4):
                            d2=math.hypot(ap[a2][0]-ap[b2][0],ap[a2][1]-ap[b2][1])
                            if d2>md:md,bp=d2,(ap[a2],ap[b2])
                    r[i]=bp;r.pop(j);ch=True
                else:j+=1
            i+=1
    lines=r
    return lines, bw

bad = ["C101_D1_P1","C10_D2_P3","C100_D1_P1"]
for stem in bad:
    gray=cv2.imread(str(IMAGES_DIR/f"{stem}_jpg.jpg"),cv2.IMREAD_GRAYSCALE)
    gt=load_gt(GT_DIR/f"{stem}_jpg.txt",*gray.shape[::-1])
    print(f"\n--- {stem} (mean={gray.mean():.1f}, GT={len(gt)}) ---")
    
    for k in [0.10,0.20,0.25,0.30,0.35]:
        lines,bw=pipe(gray,k=k)
        m=[False]*len(gt);t=f=rd=0
        for d in lines:
            bd=float("inf");bi=-1
            for gi,g in enumerate(gt):
                dist=(ptd(d[0],g[0],g[1])+ptd(d[1],g[0],g[1]))/2
                if dist<bd:bd=dist;bi=gi
            if bd<=20:
                if m[bi]:rd+=1
                else:t+=1;m[bi]=True
            else:f+=1
        fn2=sum(1 for mm in m if not mm)
        prec=t/max(t+f+rd,1);rec=t/max(t+fn2,1);f1=2*prec*rec/max(prec+rec,1e-8)
        trace=(bw>0).mean()*100
        
        cv2.imwrite(f"/tmp/gpt_{stem}_k{k:.2f}.jpg",bw)
        with open(f"/tmp/gpt_{stem}_k{k:.2f}.jpg","rb") as fh:
            b64=base64.b64encode(fh.read()).decode()
        
        r=requests.post("https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization":f"Bearer {AK}"},
            json={"model":"openai/gpt-4o-mini",
                  "messages":[{"role":"user","content":[
                      {"type":"text","text":"This image shows white wire traces on black from a circuit schematic. Rate 1-5: 1=no traces, 2=faint, 3=some visible but broken, 4=most visible and continuous, 5=crisp complete. Number only."},
                      {"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}
                  ]}],"max_tokens":5},timeout=15)
        g=r.json()["choices"][0]["message"]["content"].strip() if r.status_code==200 else "ERR"
        
        marker = " ◀ BEST F1" if f1 == max([pipe(gray,k=kk)[1].shape[0] for kk in [0.10,0.20,0.25,0.30,0.35]][:1]) else ""
        print(f"  k={k:.2f}  F1={f1:.4f}  trace={trace:.3f}%  GPT4o={g}")
