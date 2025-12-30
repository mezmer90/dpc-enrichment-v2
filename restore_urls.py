"""
Restore URLs that were incorrectly set to NULL due to overly broad pattern matching.

This script restores the 152 URLs that were incorrectly identified as placeholders
because the pattern "na" matched substrings in valid domains like "paladi-NA-health.com".
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from webapp.models import Practice

# Get database URL from environment
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///dpc_enrichment.db')
DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://')

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

# Extracted from the script output - URLs that were incorrectly nulled
URLS_TO_RESTORE = {
    'ftcjacfuzxaf': 'https://www.covenantmd.net/',
    'wjccxxwusnqr': 'https://jinnahmd.com/',
    'sttwlcbzzeku': 'https://nabhco-clinic.com/',
    'vngfxhoocmvf': 'http://monarchidealcare.com/',
    'szjzzbcbsfcv': 'https://thrivefunctionalhealth.com/',
    'numsooiwtmvm': 'http://sanctuaryfunctionalmedicine.com/',
    'tvzhvuudrruu': 'http://www.paladinahealth.com/',
    'rshvkuidygha': 'http://www.paladinahealth.com/',
    'vkixstvzoqkx': 'http://www.paladinahealth.com/',
    'ukmdutjwjrla': 'https://www.monarchfamilymedicine.com/',
    'agqcntjfkvrg': 'http://www.signaturecare.co/',
    'vganmzepmmjd': 'http://www.foundationalmed.com/',
    'giomhxqpoydc': 'http://www.yourpersonalmd.com/',
    'zslwqcifngbb': 'http://www.grandlakeshealth.com/',
    'pmiwdcjhcvwj': 'https://www.compassclinics.com/',
    'ahcfyzpptfcj': 'https://www.drloganelrod.com/',
    'ujwkemhhjxfr': 'https://viptopcare.com/',
    'qojflfwqzpny': 'https://planopremierdirect.com/',
    'wmwazxbdsbks': 'http://www.greenvalleymedicine.com/',
    'ffipibdyuhny': 'https://www.monarchhealth.com/',
    'gcuwqhpcvgck': 'http://monarchdpc.com/',
    'vpbmgxygmsjz': 'https://www.signaturemd.com/',
    'pdxdxqaxdydx': 'https://www.signaturemd.com/md/cynthia-thaik/',
    'pmiugdvnqlxh': 'http://www.signaturemd.com/md/hyman/',
    'aenqfxzvvxza': 'http://www.signaturemd.com/md/andrew-ordon/',
    'fxufqcjflppx': 'http://www.signaturemd.com/md/david-kessel/',
    'zmgbdebsiwev': 'http://www.signaturemd.com/md/diana-ramos-md/',
    'gbmwbnwjfqdc': 'https://www.signaturemd.com/maryland/baltimore/william-greenfield-dpm/',
    'vdzmebzmzqcl': 'https://www.signaturemd.com/md/charles-lee-md/',
    'lcgphgomphvw': 'https://www.signaturemd.com/locations/steven-chernoff-md/',
    'ghuubnppvyuc': 'http://monarchmd.net/',
    'nszfhpqsvlmc': 'http://www.monarchmedcare.com/',
    'vrvicuoysbze': 'https://www.signaturemd.com/md/steven-reisman/',
    'wuonzzqvfrjl': 'https://mckeowndpc.com/',
    'tfmrgauedkyi': 'https://monarchmd.com/',
    'ctvkqewmftdr': 'https://monarchclinicalcare.com/',
    'tnggjqepvqbz': 'https://monarchfamilymedicine.com/',
    'dxaadlgybffc': 'https://www.signaturemd.com/md/joseph-scherger/',
    'dcxikebrsoxv': 'http://www.signaturemd.com/md/marc-scandling/',
    'kdqobgnwrukx': 'https://www.signaturemd.com/md/william-greenfield/',
    'gkjfjstwzqcf': 'https://www.signaturemd.com/md/jeffrey-cozzens/',
    'wqmpvdbqkpjn': 'http://www.signaturemd.com/md/david-bressler/',
    'uwmgvjlxjamb': 'https://www.signaturemd.com/md/aaron-aghajanian/',
    'azvmpqkbqvay': 'https://www.signaturemd.com/md/soheila-rostami-md/',
    'iwbgnkgmmrno': 'http://www.signaturemd.com/md/leslie-mendoza-temple/',
    'gxakhjogiwdz': 'http://www.signaturemd.com/md/eric-klieninger/',
    'tbxjwmhdkxbb': 'https://signaturemd.com/md/peter-weiss/',
    'lhbgotuvpnbo': 'http://www.signaturemd.com/md/steven-reisman/',
    'fbnbuqpyxsva': 'https://monarchpc.com/',
    'mhdmghvyeqsl': 'http://www.monarchjointcare.com/',
    'bpujfqipmxgz': 'https://yourpersonalmdkid.com/',
    'vxcfxzagvkaj': 'https://www.signaturemd.com/md/deborah-longwill/',
    'rhwvfgizgppj': 'https://signaturemd.com/md/pejman-cohan/',
    'epqvjufmeksp': 'https://www.signaturemd.com/locations/drew-werner-md/',
    'yxhhphsopjrh': 'https://www.signaturemd.com/md/karen-hall/',
    'zpvzpzbhiqmx': 'https://www.signaturemd.com/md/sharon-orrange/',
    'bnaybnugsmkc': 'http://www.signaturemd.com/md/david-hoffman/',
    'ovyeaehjmqfa': 'https://www.signaturemd.com/md/karin-ried/',
    'gnvckbqndppu': 'https://www.paladinahealth.com/',
    'smatrhlrzlej': 'https://www.paladinahealth.com/',
    'uevmnfsvcrpp': 'http://monarchfamilymed.com/',
    'sqmxhjuauzaa': 'https://www.signaturemd.com/md/jeffrey-galpin/',
    'lrohngzobpjd': 'http://www.monarchfamilymedical.com/',
    'dbyeywhmqiuf': 'http://monarchfamilycare.com/',
    'ugnkkxnrxzfd': 'https://www.grandlakeshealth.com/',
    'dmxdvjqwbbll': 'https://monarchfamilycare.com/',
    'fzxsxmvtqsxw': 'https://www.signaturemd.com/md/erik-valdman/',
    'igdkehphgzbn': 'https://www.seniorhealthcarepartners.net/',
    'fghzkuhcbmwq': 'http://www.signaturemd.com/md/michelle-perkinscohen/',
    'qxbldnyxeycl': 'https://monarchmedspa.com/',
    'lczjrbdmmyxz': 'https://www.signaturemd.com/locations/gail-gross-md/',
    'otkfujwwgyvs': 'https://www.monarchpc.com/',
    'jqcwzcnfuahj': 'https://monarchseniorcare.com/',
    'puzavjbtgnjh': 'https://www.compassnaturopathic.com/',
    'uuqiryivhrrf': 'https://www.paladinahealth.com/',
    'qtbhlxtlfqit': 'https://www.signaturemd.com/md/roderick-hooker/',
    'xekqgguzxcpr': 'https://signaturemd.com/md/david-edelberg/',
    'mmpidrdblcyc': 'https://www.compassconciergemedicine.com/',
    'ldncphftbvhh': 'https://www.foundationalwellness.com/',
    'tfyhihgbdrvw': 'https://www.jinnah-md.com/',
    'ebfivzpufdvb': 'https://www.signaturemd.com/md/norman-zober/',
    'bdsqtqumvnit': 'https://www.paladinahealth.com/',
    'wvtsuwgmtjwv': 'https://monarchhealth.org/',
    'xwvcqztspfnd': 'https://signaturemd.com/md/robert-wallace/',
    'qvdbshpvusmf': 'https://www.signaturemd.com/md/mache-seibel/',
    'lpomldgvpevx': 'https://www.compassconcierge.com/',
    'ejdgjnuprvxr': 'http://www.paladinahealth.com/',
    'vqcfrpvlqgts': 'http://www.paladinahealth.com/',
    'tnbhybyqekho': 'https://www.signaturemd.com/md/charles-edelson/',
    'swgmqspkkckn': 'https://www.signaturemd.com/md/stephen-sacks-md/',
    'qzrzcnfsqopd': 'http://www.paladinahealth.com/',
    'vsdmluwtkqhw': 'https://www.signaturemd.com/md/daniel-hale/',
    'kvwxfdstgxcw': 'http://yourpersonalmd.com/',
    'wixogchppzyi': 'https://www.mdvip.com/doctors/christopher-lowe-md',
    'kwavwwdnnrrp': 'https://www.monarchprimarycare.com/',
    'bfdjhsunbfui': 'https://www.signaturemd.com/locations/alan-dappen/',
    'ubfrsnqpqerc': 'https://www.signaturemd.com/locations/mara-neibart-md/',
    'xllbjqdjwabj': 'http://www.paladinahealth.com/',
    'lrnwojunbqvw': 'https://paladinahealth.com/',
    'mpvjyftbfirr': 'http://www.paladinahealth.com/',
    'lfftmkzppkno': 'http://monarchhealthcare.com/',
    'kkzvwjpfuqnm': 'https://www.signaturemd.com/md/howard-landy/',
    'gcvlqkcpuwjd': 'https://www.signaturemd.com/md/rebecca-maidman/',
    'zxhxmfszxutl': 'https://yourpersonalmdseattle.com/',
    'bqcoxzfhiqzg': 'https://www.compassionatecarehospice.com/',
    'ndblhynpfqah': 'https://www.compasshealing.com/',
    'cpnykfzynjwm': 'https://www.grandlakedental.com/',
    'ksqjnkdnbslm': 'https://www.signaturemd.com/md/john-kennedy/',
    'zmfwgysxevcu': 'https://www.paladinahealth.com/',
    'ygtlmbnqdfkk': 'https://www.paladinahealth.com/',
    'lfkqpgfqfyfe': 'https://www.signaturemd.com/md/robert-huizenga/',
    'vmrgoaurcevg': 'http://www.monarchhealthcare.net/',
    'bpidqxljvlzj': 'https://www.seniorhealthtexas.com/',
    'qtogqhwqlfxr': 'https://www.monarchhealthcare.com/',
    'vprsdlxpmmru': 'https://compasscarehospice.com/',
    'ghnqzmlujrbh': 'http://www.paladinahealth.com/',
    'crbdnpzadtdy': 'https://www.signaturemd.com/md/laurence-lau/',
    'bskbzqlvgdha': 'https://www.signaturemd.com/md/mark-galland/',
    'yxhcrywqyccw': 'https://compassregenerative.com/',
    'jqrqyuibfhfb': 'https://www.signaturemd.com/md/robert-levine/',
    'ksvxqoqpxhhr': 'https://www.compassdoc.com/',
    'fpxntlhgjkyp': 'https://www.signaturemd.com/md/adam-davis/',
    'exoxqsqeumkk': 'http://www.paladinahealth.com/',
    'gzfxjqowcctr': 'https://www.signaturemd.com/md/gary-hubbard/',
    'fbnrlahbckyb': 'https://monarchdirect.com/',
    'uxdcpvjhztdz': 'https://monarchdirect.com/',
    'yicpbfplxbpm': 'https://www.signaturemd.com/locations/eric-nepute-dc/',
    'qwmysbrdptii': 'https://www.mdvip.com/doctors/daniel-cosgrove-md',
    'xfbxicmijwhr': 'http://www.paladinahealth.com/',
    'uuvjkpxwuwib': 'https://www.jinnah-diabetes.com/',
    'fjrvavkkrkbd': 'https://www.signaturemd.com/locations/jay-shubrook-do/',
    'twqgbwlsuvft': 'https://signaturemedicine.com/',
    'wqhouthdcngg': 'https://hipnation.com/hipnation-direct-primary-care/',
    'fmdxxthhruqd': 'https://www.nazariomd.com/',
    'ifkwhshnydhn': 'https://www.pinnaclebillings.com/',
    'iwjizpuxjugp': 'https://paladinahealth.com/',
    'lpifboxivdrp': 'https://paladinahealth.com/',
    'lkpesloopimk': 'https://paladinahealth.com/',
    'csmyshgjtqxb': 'https://paladinahealth.com/',
    'zckjcjuqmzhh': 'https://paladinahealth.com/',
    'yololhftatdw': 'https://www.primusinternalmedicine.com/',
    'vwonrlcshlvt': 'https://washingtoninternalmedicine.com/wp-content/uploads/2021/04/PATIENT-AGREEMENT-DOCTOR-DIRECT.pdf',
    'ijopzwfwbtzl': 'https://partidacorona.com/',
    'httoslzthmsz': 'https://www.soundinternalmedicine.com/',
    'ijwrilsscnfg': 'https://functionalmedcollective.com/',
    'giqovonvpagd': 'https://www.pinnacleapc.com/',
}

# Only truly invalid placeholder - the only one that should have been NULL
TRULY_INVALID = {
    'mvkzzvyxmxep': None,  # "no%20website" - this was correctly identified
    'zrgmanumxjhl': None,  # "na" - actually this one was correct too
}


def restore_urls():
    """Restore URLs that were incorrectly nulled."""

    session = Session()

    try:
        restored_count = 0
        not_found = []

        print("\nRestoring incorrectly nulled URLs...\n")

        for practice_id, url in URLS_TO_RESTORE.items():
            practice = session.query(Practice).filter_by(practice_id=practice_id).first()

            if practice:
                practice.website_url = url
                restored_count += 1
                print(f"Restored: {practice_id} -> {url}")
            else:
                not_found.append(practice_id)
                print(f"NOT FOUND: {practice_id}")

        # Commit the changes
        session.commit()
        print(f"\nSuccessfully restored {restored_count} URLs!")

        if not_found:
            print(f"\nWarning: {len(not_found)} practices not found: {not_found}")

    except Exception as e:
        print(f"\nError: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == '__main__':
    print("=" * 100)
    print("URL Restore Script")
    print("=" * 100)

    restore_urls()
