import os
import requests
import frappe

@frappe.whitelist()
def repair_broken_attachments():
    """
    Finds all files in ERPNext whose content was saved as a text URL string (https://...)
    instead of raw binary image/PDF data, and re-downloads the true binary files from QuickBooks.
    """
    settings = frappe.get_single("Quickbook Settings")
    from quickbooks_integration.api.journal_entries_sync import refresh_qb_token
    access_token = refresh_qb_token(settings) or settings.access_token
    realm_id = settings.realm_id
    base_url = "https://sandbox-quickbooks.api.intuit.com" if settings.environment == "sandbox" else "https://quickbooks.api.intuit.com"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json", "Content-Type": "application/text"}

    print("Fetching Attachable metadata from QuickBooks...")
    start = 1
    max_results = 1000
    all_atts = []
    while True:
        q = f"SELECT Id, FileName FROM Attachable STARTPOSITION {start} MAXRESULTS {max_results}"
        r = requests.post(f"{base_url}/v3/company/{realm_id}/query", headers=headers, data=q, timeout=30)
        if r.status_code != 200:
            break
        batch = r.json().get("QueryResponse", {}).get("Attachable", [])
        if not batch:
            break
        all_atts.extend(batch)
        if len(batch) < max_results:
            break
        start += max_results

    att_map = {a.get("FileName"): a.get("Id") for a in all_atts if a.get("FileName")}
    print(f"Loaded {len(att_map)} attachable filenames from QuickBooks.")

    repaired = 0
    all_files = frappe.get_all("File", fields=["name", "file_name", "is_private"])
    for f in all_files:
        folder = "private" if f.is_private else "public"
        file_path = frappe.get_site_path(folder, "files", f.file_name)
        if not os.path.exists(file_path):
            continue

        try:
            with open(file_path, "rb") as fp:
                head = fp.read(15)
        except Exception:
            continue

        # If file content is an HTTP/HTTPS text URL string instead of true binary bytes
        if head.startswith(b"http://") or head.startswith(b"https://"):
            matched_id = None
            for att_name, aid in att_map.items():
                base_att_name = os.path.splitext(att_name)[0]
                if base_att_name and base_att_name in f.file_name:
                    matched_id = aid
                    break

            if matched_id:
                try:
                    dl_url = f"{base_url}/v3/company/{realm_id}/download/{matched_id}"
                    r_dl = requests.get(dl_url, headers=headers, timeout=15)
                    if r_dl.status_code == 200:
                        signed_url = r_dl.text.strip()
                        r_img = requests.get(signed_url, timeout=30)
                        if r_img.status_code == 200 and not r_img.content.startswith(b"http"):
                            with open(file_path, "wb") as out_fp:
                                out_fp.write(r_img.content)
                            frappe.db.set_value("File", f.name, "file_size", len(r_img.content))
                            repaired += 1
                            if repaired % 50 == 0:
                                frappe.db.commit()
                                print(f"Repaired {repaired} files so far...")
                except Exception as ex:
                    print(f"Error repairing {f.file_name}: {ex}")

    frappe.db.commit()
    msg = f"Repair completed: {repaired} files successfully converted to real binary images/PDFs."
    print(msg)
    return msg
