import re
import requests
from fastapi import FastAPI

# Use a session to reuse cookies and headers for multiple requests
session = requests.Session()

app = FastAPI()


def pattern_finder(resp, pattern):
    p = re.compile(pattern)
    return p.findall(resp.text)


def generate_headers(account_no):
    url = "https://duplicatebill.wasa.punjab.gov.pk"

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Google Chrome";v="117", "Not;A=Brand";v="8", "Chromium";v="117"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }

    # Make a GET request to retrieve the initial cookies
    r = session.get(url, headers=headers)
    cookies = r.cookies.get_dict()
    cookies.update({"has_js": "1"})

    data = {}

    public_key = pattern_finder(r, 'Token(.*?)"')

    if public_key:
        key = (
            ";;System.Web.Extensions, Version=4.0.0.0, Culture=neutral, PublicKeyToken"
            + public_key[0].replace("%3d", "=").replace("%3a", ":")
        )
        data.update({"ctl00_RadScriptManager1_HiddenField": key})

    data.update({"__EVENTTARGET": "", "__EVENTARGUMENT": ""})
    viewstate = pattern_finder(r, 'id="__VIEWSTATE" value="(.*?)"')

    if viewstate:
        data.update({"__VIEWSTATE": viewstate[0]})

    viewstategenerator = pattern_finder(r, '__VIEWSTATEGENERATOR" value="(.*?)"')

    if viewstategenerator:
        data.update({"__VIEWSTATEGENERATOR": viewstategenerator[0]})

    e_valid = pattern_finder(r, '__EVENTVALIDATION" value="(.*?)"')

    if e_valid:
        data.update({"__EVENTVALIDATION": e_valid[0]})

    data.update(
        {
            "ctl00$MainContent$txtAccountNo": str(account_no),
            "ctl00$MainContent$btnSubmit": "Submit",
        }
    )

    return data, cookies, url


def hit_account(account_no, data, cookies, url):
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": url,
        "Referer": f"{url}/duplicate_bill.aspx",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Google Chrome";v="117", "Not;A=Brand";v="8", "Chromium";v="117"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }

    # Make a POST request using the session and provided data
    response = session.post(
        f"{url}/duplicate_bill.aspx", cookies=cookies, headers=headers, data=data
    )
    return response


def cleaner(lsts):
    temp = " ".join([i for i in lsts if i != ""])
    return temp.replace("&nbsp;", " ")


def patterns_matches(tag, response):
    pattern = re.compile(f"{tag}.*?<span.*?>(.*?)<")
    return cleaner(pattern.findall(response.text))


def extract_info(account_no):
    data, cookies, url = generate_headers(account_no)
    res = hit_account(account_no, data, cookies, url)

    info = {}

    pattern = re.compile(f"Sorry.*?!")
    not_found = pattern.findall(res.text)

    if not_found:
        info.update({account_no: {"name": "Record Not Found"}})

    else:
        name = patterns_matches("Name", res).strip()
        address = patterns_matches("ADDR", res).strip()
        ward = patterns_matches("WardNoWARDNUMR91", res).strip()
        account_no = patterns_matches("AcNoACCTNUMR81", res).strip()
        property_no = patterns_matches("PropertyNoPPTYNUMR101", res).strip()
        type_ = patterns_matches("BILLSYSTDESCWH171", res).strip()
        connection = patterns_matches("ConnectionTypeCONDES361", res).strip()
        amount_due_date = patterns_matches("AmountPayableRoundTCURDUES251", res).strip()
        amount_after_date = patterns_matches(
            "AmountPayableRoundTAMTAFDUE291", res
        ).strip()
        demand = patterns_matches("TotalCurrentDemandTCURDMND231", res).strip()
        arrears = patterns_matches("ArrearsBFTARERBF241", res).strip()
        raqba = patterns_matches("AreaAREAMRLA121", res).strip()
        start = patterns_matches("BillingPeriodFromPERDSTRTD312", res).strip()
        end = patterns_matches("BillingPeriodToPERDENDDA322", res).strip()
        issue_date = patterns_matches("IssueDate131", res)
        due_date = patterns_matches("DueDateCURRDUEDA161", res)

        info.update(
            {
                account_no: {
                    "name": name,
                    "address": address,
                    "ward": ward,
                    "account_no": account_no,
                    "property_no": property_no,
                    "type": type_,
                    "connection": connection,
                    "amount_due_date": amount_due_date.split(".")[0],
                    "amount_after_date": amount_after_date.split(".")[0],
                    "demand": demand.split(".")[0],
                    "arrears": arrears.split(".")[0],
                    "raqba": raqba,
                    "time_period": f"From {start} TO {end}",
                    "issue_date": issue_date,
                    "due_date": due_date,
                }
            }
        )
    return info


@app.get("/")
async def read_item():
    """Welcome message."""
    return {"data": "Welcome to the API!"}


@app.get("/account/{item_id}")
async def account(item_id: int):
    """Get account information by account number."""

    account_info = extract_info(item_id)

    if (
        account_info.get(item_id)
        and account_info[item_id]["name"] == "Record Not Found"
    ):
        return {"error": "Account not found"}
    return {"data": account_info}
