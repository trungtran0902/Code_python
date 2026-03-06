from duckduckgo_search import DDGS
import pandas as pd
import time

df = pd.read_excel("merchant name.xlsx")

df["MerchantName"] = ""
df["Snippet"] = ""

ddgs = DDGS()

for idx, row in df.iterrows():
    keyword = row["Name of building"]
    print("Searching:", keyword)

    try:
        results = ddgs.text(keyword, max_results=1)
        if results:
            df.at[idx, "MerchantName"] = results[0]["title"]
            df.at[idx, "Snippet"] = results[0]["body"]
        else:
            df.at[idx, "MerchantName"] = "Not found"
    except:
        df.at[idx, "MerchantName"] = "Error"

    time.sleep(1)

df.to_excel("merchant_output.xlsx", index=False)
print("Done!")
