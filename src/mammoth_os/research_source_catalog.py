"""Publicly attributed state wildlife homepages, checked 2026-11-02.

AFWA represents state fish/wildlife agencies; its member directory supplies all
50 state entries (Pennsylvania has separate game and fish agencies). Government
pages/redirects additionally corroborate every non-government hostname below.
This is directory attribution, not claim verification or a live-uptime promise.
Some agency servers block automated access; directory links remain inspectable.
Ohio's listed endpoint redirects to a government page returning HTTP 404;
Mississippi's HTTPS endpoint failed local certificate validation. Neither
condition is presented as successful page retrieval or factual verification.
No network requests occur when importing or using this catalog.
"""
from urllib.parse import urlsplit


DIRECTORY_SOURCE = "https://www.fishwildlife.org/landing/membership/member-list"
CHECKED_ON = "2026-11-02"

# Exact targets read from the AFWA directory; preserve these for provenance even
# when a directly observed redirect supplies the current homepage below.
_DIRECTORY_TARGETS = {
    "alabama": "http://www.outdooralabama.com/about-us/wildlife-and-freshwater-fisheries-division",
    "alaska": "http://www.adfg.alaska.gov/",
    "arizona": "https://www.azgfd.com/",
    "arkansas": "https://www.agfc.com/en/",
    "california": "https://www.wildlife.ca.gov/",
    "colorado": "http://cpw.state.co.us/",
    "connecticut": "https://portal.ct.gov/deep/about/main/natural-resources",
    "delaware": "https://dnrec.alpha.delaware.gov/fish-wildlife/",
    "florida": "http://www.myfwc.com/",
    "georgia": "http://georgiawildlife.com/",
    "hawaii": "http://dlnr.hawaii.gov/",
    "idaho": "https://idfg.idaho.gov/",
    "illinois": "https://www.dnr.illinois.gov/Pages/default.aspx",
    "indiana": "https://www.in.gov/dnr/fish-and-wildlife/",
    "iowa": "http://www.iowadnr.gov/",
    "kansas": "http://ksoutdoors.com/",
    "kentucky": "https://fw.ky.gov/Pages/default.aspx",
    "louisiana": "http://www.wlf.louisiana.gov/",
    "maine": "https://www.maine.gov/IFW/",
    "maryland": "http://dnr.maryland.gov/wildlife/Pages/default.aspx",
    "massachusetts": "https://www.mass.gov/orgs/division-of-fisheries-and-wildlife",
    "michigan": "http://www.michigan.gov/dnr/",
    "minnesota": "http://www.dnr.state.mn.us/fishwildlife/index.html",
    "mississippi": "http://www.mdwfp.com/",
    "missouri": "https://mdc.mo.gov/",
    "montana": "http://fwp.mt.gov/",
    "nebraska": "http://outdoornebraska.gov/",
    "nevada": "http://www.ndow.org/",
    "new hampshire": "https://www.wildlife.nh.gov/",
    "new jersey": "http://www.state.nj.us/dep/fgw/",
    "new mexico": "https://wildlife.dgf.nm.gov/",
    "new york": "http://www.dec.ny.gov/",
    "north carolina": "https://www.ncwildlife.org/",
    "north dakota": "https://gf.nd.gov",
    "ohio": "http://wildlife.ohiodnr.gov/",
    "oklahoma": "https://www.wildlifedepartment.com/",
    "oregon": "https://myodfw.com/",
    "pennsylvania": "http://www.pgc.pa.gov/Pages/default.aspx",
    "rhode island": "http://www.dem.ri.gov/",
    "south carolina": "http://www.dnr.sc.gov/",
    "south dakota": "https://gfp.sd.gov/",
    "tennessee": "https://www.tn.gov/twra/",
    "texas": "https://tpwd.texas.gov/",
    "utah": "https://wildlife.utah.gov/",
    "vermont": "http://www.vtfishandwildlife.com/",
    "virginia": "https://dwr.virginia.gov",
    "washington": "https://wdfw.wa.gov/",
    "west virginia": "http://www.wvdnr.gov/",
    "wisconsin": "http://dnr.wi.gov/",
    "wyoming": "https://wgfd.wyo.gov/",
}

# Observed HTTPS redirects, plus Illinois's directly reachable government
# homepage replacing the directory's 404 legacy path.
_CURRENT_URLS = {
    "arkansas": "https://www.agfc.com/",
    "california": "https://wildlife.ca.gov/",
    "florida": "https://myfwc.com/",
    "illinois": "https://dnr.illinois.gov/",
    "new jersey": "https://www.nj.gov/dep/fgw/",
    "new york": "https://dec.ny.gov/",
    "north carolina": "https://www.ncwildlife.gov/",
    "ohio": "https://ohiodnr.gov/wps/portal/gov/odnr/discover-and-learn/safety-conservation/about-ODNR/wildlife",
    "pennsylvania": "https://www.pa.gov/agencies/pgc",
    "wisconsin": "https://dnr.wisconsin.gov/",
}

# Independent own-state corroboration of non-government directory targets.
# Arizona's government URL was checked without following redirects: HTTP 301
# Location: https://www.azgfd.com/ (the destination blocks automated GETs).
_STATE_CONFIRMATIONS = {
    "alabama": "https://inform.alabama.gov/agencies/Details/5",
    "arizona": "https://www.azgfd.gov/",
    "arkansas": "https://portal.arkansas.gov/state_agencies/arkansas-state-game-and-fish-commission/",
    "florida": "https://dos.fl.gov/library-archives/research/florida-information/government/state-resources/state-agency-homepages/",
    "georgia": "https://georgia.gov/organization/georgia-department-natural-resources-wildlife-resources-division",
    "kansas": "https://portal.kansas.gov/government/agency-list/",
    "mississippi": "https://www.ms.gov/agencies/department-wildlife-fisheries-and-parks",
    "nevada": "https://veterans.nv.gov/veteran-resources/nvtap/hunting-fishing-licenses/",
    "north carolina": "https://www.nc.gov/state-north-carolina-directory",
    "oklahoma": "https://oklahoma.gov/",
    "oregon": "https://www.dfw.state.or.us/",
    "vermont": "https://www.vermont.gov/government/agency-a-z",
}

STATE_WILDLIFE_CATALOG = {
    state: {
        "url": _CURRENT_URLS.get(state, listed_url),
        "listed_url": listed_url,
        "directory_source": DIRECTORY_SOURCE,
        "checked_on": CHECKED_ON,
        **({"state_confirmation": _STATE_CONFIRMATIONS[state]} if state in _STATE_CONFIRMATIONS else {}),
    }
    for state, listed_url in _DIRECTORY_TARGETS.items()
}
STATE_WILDLIFE_CATALOG["illinois"]["state_confirmation"] = "https://dnr.illinois.gov/"
STATE_WILDLIFE_CATALOG["pennsylvania"]["state_confirmation"] = "https://www.pa.gov/agencies/fishandboat"
STATE_WILDLIFE_CATALOG["ohio"]["access_note"] = "Directory target redirects; destination returned HTTP 404."
STATE_WILDLIFE_CATALOG["mississippi"]["access_note"] = "HTTPS target failed local certificate validation; TLS checks were not disabled."
STATE_WILDLIFE_CATALOG["pennsylvania"]["additional_agencies"] = [{
    "url": "https://www.pa.gov/agencies/fishandboat",
    "listed_url": "http://www.fishandboat.com/Pages/default.aspx",
    "directory_source": DIRECTORY_SOURCE,
}]

# Exact aliases observed in the government confirmations or direct redirects.
# Do not implicitly authorize www or arbitrary subdomains of non-government
# hosts. The directory's legacy fishandboat.com target redirects to pa.gov.
_CONFIRMED_ALIASES = {
    "outdooralabama.com": "alabama",
    "agfc.com": "arkansas",
    "myfwc.com": "florida",
    "vtfishandwildlife.com": "vermont",
    "www.fishandboat.com": "pennsylvania",
}

STATE_WILDLIFE_HOSTS = {
    urlsplit(record[field]).hostname: state
    for state, record in STATE_WILDLIFE_CATALOG.items()
    for field in ("url", "listed_url")
}
STATE_WILDLIFE_HOSTS.update(_CONFIRMED_ALIASES)

# Only these exact non-government hosts get the directory-based authority tier.
OFFICIAL_STATE_WILDLIFE_HOSTS = {
    host: state for host, state in STATE_WILDLIFE_HOSTS.items()
    if not host.endswith(".gov") and ".state." not in host
}
