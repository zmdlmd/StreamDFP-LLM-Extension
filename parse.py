import sys
import math
import time
import pandas as pd
import numpy as np
ls_measure = [
    "classified instances", "classifications correct (percent)",
    "Kappa Statistic (percent)", "Kappa Temporal Statistic (percent)",
    "Kappa M Statistic (percent)", "TP", "FP", "TN", "FN",
    "False Alarm Rate (percent)", "Average Days before Failure",
    "F1 Score (percent)", "F1 Score for class 0 (percent)",
    "F1 Score for class 1 (percent)", "Precision (percent)",
    "Precision for class 0 (percent)", "Precision for class 1 (percent)",
    "Recall (percent)", "Recall for class 0 (percent)",
    "Recall for class 1 (percent)"
]
dict_ = {
    "classified instances": "clf_insts",
    "classifications correct (percent)": "clf_corrct",
    "Kappa Statistic (percent)": "Kappa",
    "Kappa Temporal Statistic (percent)": "Kappa_temp",
    "Kappa M Statistic (percent)": "Kappa_M",
    "TP": "TP",
    "FP": "FP",
    "TN": "TN",
    "FN": "FN",
    "False Alarm Rate (percent)": "FAR",
    "Average Days before Failure": "Days",
    "F1 Score (percent)": "F1_score",
    "F1 Score for class 0 (percent)": "F1_score_c0",
    "F1 Score for class 1 (percent)": "F1_score_c1",
    "Precision (percent)": "Precision",
    "Precision for class 0 (percent)": "Precision_c0",
    "Precision for class 1 (percent)": "Precision_c1",
    "Recall (percent)": "Recall",
    "Recall for class 0 (percent)": "Recall_c0",
    "Recall for class 1 (percent)": "Recall_c1"
}
date = ""
expected_len = 41  # 1 date + 20 global + 20 local
progress_every_lines = 20000


def normalize_row(row, target_len):
    if len(row) < target_len:
        return row + [np.nan] * (target_len - len(row))
    if len(row) > target_len:
        return row[:target_len]
    return row


start_ts = time.time()
with open(sys.argv[1], "r") as f:
    res = []
    res_row = []
    for line_no, line in enumerate(f, start=1):
        if line_no == 1 or line_no % progress_every_lines == 0:
            elapsed = max(time.time() - start_ts, 1e-6)
            rate = line_no / elapsed
            print(f"[parse.py] lines={line_no} rate={rate:.1f} lines/s", file=sys.stderr, flush=True)
        if line[0:3] == "201":
            date = line[0:10]
            if len(res_row) > 0:
                res.append(normalize_row(res_row, expected_len))
                res_row = []
            res_row.append(date)
        elif "Global Measurements" in line:
            continue
        elif "Local Measurements" in line:
            continue
            #if res is not None:
            #    for item in res:
            #        print(item, end=" ")
            #    print("")
            #flag = 1
            #res = []
        elif "Model measurements" in line:
            continue
        elif "None" in line:
            continue
        elif "time" in line:
            continue
        elif "Index" in line:
            continue
        elif "reset" in line:
            continue
        elif "num drifts" in line:
            continue
        elif "Votes" in line:
            continue
        elif line[0] == "\n":
            continue
        elif "Using" in line:
            continue
        elif "model" in line:
            continue
        elif "tree" in line:
            continue
        elif "leaves" in line:
            continue
        elif "leaf" in line:
            continue
        elif "byte" in line:
            continue
        elif "get" in line:
            continue
        elif "num iterations" in line:
            continue
        elif "prediction time" in line:
            continue
        elif "training time" in line:
            continue
        else:
            res_row.append(line.strip().split(" ")[-1])
if len(res_row) > 0:
    res.append(normalize_row(res_row, expected_len))
print(f"[parse.py] parsed_rows={len(res)} elapsed={time.time()-start_ts:.1f}s", file=sys.stderr, flush=True)

columns_name = ['date']
for item in ls_measure:
    columns_name.append("g_%s" % dict_[item])
for item in ls_measure:
    columns_name.append("l_%s" % dict_[item])

df = pd.DataFrame(res, columns=columns_name)
df.to_csv(sys.argv[1][:-4] + ".csv", index=False)
df = df.dropna(how="all", axis=0)
for col in [
        'l_Days', 'l_FP', 'l_FAR', 'l_F1_score_c1', 'l_Precision_c1',
        'l_Recall_c1'
]:
    df[col] = pd.to_numeric(df[col], errors='coerce')

df_metric = df[df['l_Recall_c1'].notna()]
print("days\t\tFP\t\tFPR\t\tF1-score\tPrecision\tRecall")
if len(df_metric) == 0:
    print("NaN\tNaN\tNaN\tNaN\tNaN\tNaN")
else:
    days_mean = df_metric['l_Days'].mean()
    fp_mean = df_metric['l_FP'].mean()
    far_mean = df_metric['l_FAR'].mean()
    p_mean = df_metric['l_Precision_c1'].mean()
    r_mean = df_metric['l_Recall_c1'].mean()
    f1_mean = 2.0 * p_mean * r_mean / (p_mean + r_mean)
    print("%lf\t%lf\t%lf\t%lf\t%lf\t%lf" % (days_mean, fp_mean, far_mean,
                                            f1_mean, p_mean, r_mean))
