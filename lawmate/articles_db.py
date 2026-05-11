"""lawmate — 台灣民眾日常法律條文 corpus(純函式 / no I/O / no LLM).

涵蓋 30 條最常用條文,分為 6 大類:
  - 勞基法 (LSA)
  - 民法 (CIV)
  - 消保法 (CPA)
  - 道交條例 (TRA)
  - 公寓大廈管理條例 (APT)
  - 個資法 / 職業安全 (DPA / OSH)

每條 Article 含 title / law_source / article_number / text / keywords /
scenarios。用於 BM25 索引時將 text + keywords + scenarios 串接。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Article:
    article_id: str
    law_source: str                   # 勞基法 / 民法 / ...
    article_number: str               # 第 24 條 / 第 421 條
    title: str                        # 短描述
    text: str                         # 條文內容(節錄)
    keywords: tuple[str, ...] = ()    # 適用情境關鍵字
    scenarios: tuple[str, ...] = ()   # 常見適用情境
    application_hint: str = ""        # 一般民眾如何引用


# ========== 勞基法 (LSA) ==========
ARTICLES: list[Article] = [
    Article(
        article_id="LSA-24",
        law_source="勞動基準法",
        article_number="第 24 條",
        title="延長工時加班費",
        text="雇主延長勞工工作時間者,其延長工作時間之工資依下列標準加給之:一、平日每日延長工作時間在 2 小時以內者,按平日每小時工資額加給三分之一以上。二、再延長工作時間在 2 小時以內者,按平日每小時工資額加給三分之二以上。",
        keywords=("加班費", "延長工時", "加班", "工時", "三分之一", "三分之二", "OT"),
        scenarios=("我加班沒拿到加班費", "公司不給加班費", "我加班費被少算"),
        application_hint="雇主應給加班費,不可口頭協議『不算加班』或『補休抵加班費』。",
    ),
    Article(
        article_id="LSA-32",
        law_source="勞動基準法",
        article_number="第 32 條",
        title="加班時數上限",
        text="雇主有使勞工在正常工作時間以外工作之必要者,經工會同意 ... 延長工作時間,一日不得超過 12 小時,延長之工作時間,一個月不得超過 46 小時。",
        keywords=("加班時數", "上限", "46 小時", "每月加班", "延長工時"),
        scenarios=("公司一個月叫我加班 60 小時", "加班超時違法嗎"),
        application_hint="一個月加班合計不可超過 46 小時。超過可向勞工局申訴。",
    ),
    Article(
        article_id="LSA-16",
        law_source="勞動基準法",
        article_number="第 16 條",
        title="雇主終止契約預告期",
        text="雇主依第 11 條或第 13 條但書規定終止勞動契約者,其預告期間依下列規定:一、繼續工作 3 個月以上 1 年未滿者,於 10 日前預告之。二、繼續工作 1 年以上 3 年未滿者,於 20 日前預告之。三、繼續工作 3 年以上者,於 30 日前預告之。",
        keywords=("資遣", "預告期", "解僱", "終止勞動契約", "10 日", "20 日", "30 日"),
        scenarios=("公司今天通知明天不用來", "突然被資遣", "解僱沒給預告期"),
        application_hint="公司未給足預告期應發預告期工資(原預告期天數 × 平日工資)。",
    ),
    Article(
        article_id="LSA-17",
        law_source="勞動基準法",
        article_number="第 17 條",
        title="資遣費計算",
        text="雇主依前條(第 11、13 條但書)終止勞動契約者,應依下列規定發給勞工資遣費:一、在同一雇主之事業單位繼續工作,每滿 1 年發給相當於 1 個月平均工資之資遣費。二、依前款計算之剩餘月數,或工作未滿 1 年者,以比例計給之。",
        keywords=("資遣費", "終止契約", "平均工資", "服務年資"),
        scenarios=("被資遣有資遣費嗎", "資遣費怎麼算", "公司倒閉資遣費"),
        application_hint="勞退新制下資遣費上限為 6 個月平均工資(新制 §12)。",
    ),
    Article(
        article_id="LSA-38",
        law_source="勞動基準法",
        article_number="第 38 條",
        title="特別休假",
        text="勞工在同一雇主或事業單位,繼續工作滿一定期間者,應依下列規定給予特別休假:6 個月以上未滿 1 年:3 日;1 年以上未滿 2 年:7 日;2 年以上未滿 3 年:10 日;3 年以上未滿 5 年:每年 14 日;5 年以上未滿 10 年:每年 15 日;10 年以上:每 1 年加給 1 日,加至 30 日為止。",
        keywords=("特休", "特別休假", "年資", "休假", "未休完工資"),
        scenarios=("我特休不夠用", "離職特休沒休完怎麼辦", "特休天數計算"),
        application_hint="特休未休完,雇主應發給工資;或當年度勞資協議遞延 1 年。",
    ),
    Article(
        article_id="LSA-22",
        law_source="勞動基準法",
        article_number="第 22 條",
        title="工資全額給付原則",
        text="工資之給付應全額直接給付勞工。但法令另有規定或勞雇雙方另有約定者,不在此限。工資應每月至少定期發給 2 次,並應提供工資各項目計算方式明細。",
        keywords=("工資扣減", "薪水", "薪資", "扣薪", "發薪日", "薪資明細"),
        scenarios=("公司扣我薪水", "薪水沒準時發", "薪資沒明細"),
        application_hint="未經勞工書面同意不可任意扣薪;遲發工資可向勞工局申訴。",
    ),

    # ========== 民法 (CIV) ==========
    Article(
        article_id="CIV-421",
        law_source="民法",
        article_number="第 421 條",
        title="租賃契約定義",
        text="稱租賃者,謂當事人約定,一方以物租與他方使用、收益,他方支付租金之契約。",
        keywords=("租賃", "租屋", "出租", "承租", "租約"),
        scenarios=("租屋糾紛", "口頭租約算數嗎"),
        application_hint="租賃契約可口頭成立,但建議書面便於舉證。",
    ),
    Article(
        article_id="CIV-179",
        law_source="民法",
        article_number="第 179 條",
        title="不當得利",
        text="無法律上之原因而受利益,致他人受損害者,應返還其利益。雖有法律上之原因,而其後已不存在者,亦同。",
        keywords=("不當得利", "返還", "退款", "退錢", "誤匯款"),
        scenarios=("匯錯款項對方不還", "對方收了錢卻沒提供服務"),
        application_hint="可主張不當得利請求返還;追訴時效 15 年。",
    ),
    Article(
        article_id="CIV-184",
        law_source="民法",
        article_number="第 184 條",
        title="侵權行為損害賠償",
        text="因故意或過失,不法侵害他人之權利者,負損害賠償責任。故意以背於善良風俗之方法,加損害於他人者亦同。違反保護他人之法律,致生損害於他人者,負賠償責任。",
        keywords=("侵權", "損害賠償", "車禍", "鄰居噪音", "毀損", "傷害"),
        scenarios=("車禍對方該賠多少", "鄰居噪音影響我家", "東西被弄壞要賠"),
        application_hint="是台灣最常引用的侵權條款。賠償包含醫療費 / 工作損失 / 精神慰撫金 / 車輛維修。",
    ),
    Article(
        article_id="CIV-250",
        law_source="民法",
        article_number="第 250 條",
        title="違約金約定",
        text="當事人得約定債務人於債務不履行時,應支付違約金。違約金,除當事人另有訂定外,視為因不履行而生損害之賠償總額。",
        keywords=("違約金", "提前解約", "賠償", "押金", "罰金"),
        scenarios=("提前解約要賠多少違約金", "違約金是否合理", "押金被沒收"),
        application_hint="法院得依職權酌減違約金(§252)。一般 1 個月租金為合理上限。",
    ),
    Article(
        article_id="CIV-125",
        law_source="民法",
        article_number="第 125 條",
        title="一般時效",
        text="請求權,因 15 年間不行使而消滅。但法律所定期間較短者,依其規定。",
        keywords=("時效", "消滅時效", "請求權"),
        scenarios=("舊債還能討嗎", "時效已過要怎麼辦"),
        application_hint="一般請求權 15 年。利息 5 年(§126),勞工權利 5 年(勞基 §58)。",
    ),

    # ========== 消保法 (CPA) ==========
    Article(
        article_id="CPA-19",
        law_source="消費者保護法",
        article_number="第 19 條",
        title="通訊交易 7 日鑑賞期",
        text="通訊交易或訪問交易之消費者,得於收受商品或接受服務後 7 日內,以退回商品或書面通知方式解除契約,無須說明理由及負擔任何費用或對價。",
        keywords=("7 日鑑賞期", "網購", "通訊交易", "退貨", "蝦皮", "PChome"),
        scenarios=("網購想退貨", "蝦皮買到不適合", "通訊交易 7 天無理由退"),
        application_hint="7 日內可無理由退,賣家不可拒。但易腐 / 客製 / 報紙等有例外。",
    ),
    Article(
        article_id="CPA-17",
        law_source="消費者保護法",
        article_number="第 17 條",
        title="定型化契約應記載 / 不得記載事項",
        text="中央主管機關得選擇特定行業,參酌定型化契約條款之性質、合理之交易習慣、社會經濟狀況及其他事項,公告其定型化契約應記載或不得記載之事項。",
        keywords=("定型化契約", "霸王條款", "應記載", "不得記載", "租賃合約"),
        scenarios=("房東給的合約有奇怪條款", "電信續約被綁很久"),
        application_hint="違反應記載 / 不得記載事項的條款無效,可主張不受拘束。",
    ),
    Article(
        article_id="CPA-7",
        law_source="消費者保護法",
        article_number="第 7 條",
        title="商品 / 服務無過失責任",
        text="從事設計、生產、製造商品或提供服務之企業經營者,應確保其提供之商品或服務,無安全或衛生上之危險。商品或服務具有危害消費者生命、身體、健康、財產之可能者,應於明顯處為警告標示及緊急處理危險之方法。",
        keywords=("商品瑕疵", "食品安全", "服務瑕疵", "無過失責任"),
        scenarios=("買到瑕疵商品", "食物吃了不舒服", "服務有問題受傷"),
        application_hint="企業經營者負無過失責任 — 即使無過失也應負損害賠償。",
    ),

    # ========== 道路交通管理處罰條例 (TRA) ==========
    Article(
        article_id="TRA-35",
        law_source="道路交通管理處罰條例",
        article_number="第 35 條",
        title="酒駕處罰",
        text="汽車駕駛人,駕駛汽車經測試檢定酒精濃度超過規定標準者,處新臺幣 3 萬元以上 12 萬元以下罰鍰,並當場移置保管該汽車及吊扣其駕駛執照 1 年。",
        keywords=("酒駕", "酒測", "吊照", "0.15", "罰金"),
        scenarios=("被開酒駕罰單", "酒駕初犯怎麼辦"),
        application_hint="酒測超 0.15 罰 3-12 萬 + 吊扣 1 年;超 0.25 致人傷亡可能刑事追訴。",
    ),
    Article(
        article_id="TRA-53",
        law_source="道路交通管理處罰條例",
        article_number="第 53 條",
        title="闖紅燈處罰",
        text="汽車駕駛人,行經有燈光號誌管制之交岔路口闖紅燈者,處新臺幣 1,800 元以上 5,400 元以下罰鍰。",
        keywords=("闖紅燈", "紅燈", "違規記點"),
        scenarios=("被開闖紅燈罰單", "右轉是否算闖紅燈"),
        application_hint="罰款 1,800-5,400 + 記違規點數 3 點。可申訴若有疑義。",
    ),
    Article(
        article_id="TRA-40",
        law_source="道路交通管理處罰條例",
        article_number="第 40 條",
        title="超速處罰",
        text="汽車駕駛人,行車速度超過規定之最高時速,處新臺幣 1,200 元以上 2,400 元以下罰鍰。",
        keywords=("超速", "速限", "測速照相"),
        scenarios=("被開超速罰單"),
        application_hint="罰款 1,200-2,400(超 20 km 內);超 40 km 處 3,000-6,000 + 吊扣。",
    ),

    # ========== 公寓大廈管理條例 (APT) ==========
    Article(
        article_id="APT-10",
        law_source="公寓大廈管理條例",
        article_number="第 10 條",
        title="共用部分修繕",
        text="專有部分、約定專用部分之修繕、管理、維護,由各該區分所有權人或約定專用部分之使用人為之 ... 共用部分、約定共用部分之修繕、管理、維護,由管理負責人或管理委員會為之。",
        keywords=("漏水", "公寓修繕", "管委會", "共用部分", "天花板漏水"),
        scenarios=("天花板漏水誰要修", "外牆滲水", "頂樓漏水"),
        application_hint="共用部分由管委會修;專有部分由區分所有權人自負。漏水到別人家可能涉侵權。",
    ),
    Article(
        article_id="APT-16",
        law_source="公寓大廈管理條例",
        article_number="第 16 條",
        title="區分所有權人義務 / 安寧",
        text="區分所有權人及住戶,不得任意棄置垃圾、排放各種污染物、惡臭物質或發生喧囂、振動及其他與此相類之行為。",
        keywords=("噪音", "鄰居", "妨害安寧", "深夜噪音", "裝修"),
        scenarios=("鄰居半夜製造噪音", "樓上小孩跑步聲擾人"),
        application_hint="先以管委會調解;不成可報警依社會秩序維護法或提告侵權。",
    ),

    # ========== 個人資料保護法 (DPA) ==========
    Article(
        article_id="DPA-5",
        law_source="個人資料保護法",
        article_number="第 5 條",
        title="個資蒐集限制",
        text="個人資料之蒐集、處理或利用,應尊重當事人之權益,依誠實及信用方法為之,不得逾越特定目的之必要範圍,並應與蒐集之目的具有正當合理之關聯。",
        keywords=("個資", "蒐集", "個人資料", "授權", "侵犯隱私"),
        scenarios=("公司問太多私事", "莫名收到推銷電話", "我的資料被外洩"),
        application_hint="可主張刪除 / 停止利用;違法蒐集可向個資保護委員會檢舉。",
    ),

    # ========== 性騷擾防治法 (SHA) ==========
    Article(
        article_id="SHA-13",
        law_source="性騷擾防治法",
        article_number="第 13 條",
        title="性騷擾被害人申訴",
        text="性騷擾事件被害人除可依相關法律請求損害賠償外,亦得直接向加害人提出申訴。性騷擾事件之發生於公私立各級學校教學環境者,適用性別平等教育法。",
        keywords=("性騷擾", "申訴", "工作場所", "性別歧視"),
        scenarios=("被同事騷擾", "主管不當對待", "職場性騷擾"),
        application_hint="工作場所性騷擾向雇主申訴(性平法);其他場所向加害人住居所地警察機關。",
    ),

    # ========== 勞工保險條例 (LIA) ==========
    Article(
        article_id="LIA-34",
        law_source="勞工保險條例",
        article_number="第 34 條",
        title="職業傷害補助",
        text="被保險人因職業傷害或職業病不能工作,以致未能取得原有薪資,正在治療中者,自不能工作之第 4 日起,發給職業傷害補償費或職業病補償費。",
        keywords=("職災", "工傷", "職業傷害", "職業病", "勞保給付"),
        scenarios=("上班受傷怎麼辦", "通勤車禍算職災嗎", "肝炎是職業病嗎"),
        application_hint="第 4 天起發補償(70% 投保薪資 × 6 月內);通勤事故符合條件也算職災。",
    ),

    # ========== 道交 + 民法侵權合用 ==========
    Article(
        article_id="CIV-191-2",
        law_source="民法",
        article_number="第 191-2 條",
        title="動力車輛駕駛人責任",
        text="汽車、機車或其他非依軌道行駛之動力車輛,在使用中加損害於他人者,駕駛人應賠償因此所生之損害。但於防止損害之發生,已盡相當之注意者,不在此限。",
        keywords=("車禍", "駕駛人責任", "汽車", "機車", "肇事"),
        scenarios=("被汽車撞", "機車車禍誰賠", "肇事責任比例"),
        application_hint="駕駛人推定有過失,需舉證『已盡相當注意』才能免責。",
    ),

    # ========== 民法 - 連帶債務 / 保證 ==========
    Article(
        article_id="CIV-272",
        law_source="民法",
        article_number="第 272 條",
        title="連帶債務",
        text="數人負同一債務,明示對於債權人各負全部給付之責任者,為連帶債務。無前項之明示時,連帶債務之成立,以法律有規定者為限。",
        keywords=("連帶保證", "保證人", "債務", "信用卡保證", "簽連帶"),
        scenarios=("幫朋友當保證人怎麼辦", "他不還錢我要還嗎"),
        application_hint="連帶保證 = 你跟主債務人同等責任。普通保證 = 主債務人沒能力時你才賠。",
    ),

    # ========== 民法 - 不動產物權 ==========
    Article(
        article_id="CIV-758",
        law_source="民法",
        article_number="第 758 條",
        title="不動產物權登記",
        text="不動產物權,依法律行為而取得、設定、喪失及變更者,非經登記,不生效力。前項行為,應以書面為之。",
        keywords=("不動產", "登記", "過戶", "房屋買賣", "繼承"),
        scenarios=("房子買賣未登記算有效嗎", "父親過世未過戶"),
        application_hint="不動產買賣必須完成登記才生效。未登記前不能對抗第三人。",
    ),

    # ========== 公寓大廈管理條例 - 違規裝修 ==========
    Article(
        article_id="APT-8",
        law_source="公寓大廈管理條例",
        article_number="第 8 條",
        title="共用部分變更限制",
        text="公寓大廈周圍上下、外牆面、樓頂平臺及不屬專有部分之防空避難設備,其變更構造、顏色、設置廣告物、鐵鋁窗或其他類似之行為,除應依法令規定辦理外,該公寓大廈規約另有規定或區分所有權人會議已有決議,並經 ... ",
        keywords=("外牆變更", "鐵窗", "違建", "頂樓加蓋", "違規裝修"),
        scenarios=("鄰居加蓋頂樓", "外牆裝鐵窗合法嗎", "違規違建"),
        application_hint="變更外觀需區分所有權人會議決議。違規可向縣市政府舉發。",
    ),

    # ========== 道交條例 - 肇事責任 / 不依規定保持距離 ==========
    Article(
        article_id="TRA-94",
        law_source="道路交通管理處罰條例",
        article_number="第 94 條",
        title="未保持安全距離",
        text="汽車駕駛人,不按遵行之方向行駛或不依規定駛入來車道,處新臺幣 600 元以上 1,800 元以下罰鍰。汽車駕駛人,駕駛汽車不保持安全距離,致發生交通事故者,處 ...",
        keywords=("安全距離", "追撞", "未保持距離"),
        scenarios=("我被後方追撞", "未保持安全距離"),
        application_hint="未保持安全距離致追撞,後車通常需負主要責任。",
    ),

    # ========== 勞基法 - 工作規則 / 試用期 ==========
    Article(
        article_id="LSA-70",
        law_source="勞動基準法",
        article_number="第 70 條",
        title="工作規則",
        text="雇主僱用勞工人數在 30 人以上者,應依其事業性質,就下列事項訂立工作規則,報請主管機關核備後並公開揭示之:工作時間、休息、休假 ... 工資之標準、計算方法及發放日期。",
        keywords=("工作規則", "試用期", "考勤", "工時規定"),
        scenarios=("試用期可以無預警 fire 我嗎", "工作規則應公開"),
        application_hint="台灣沒有明文『試用期』,試用期辭退仍需依勞基 §11 / §12 法定事由。",
    ),

    # ========== 個資法 - 當事人權利 ==========
    Article(
        article_id="DPA-3",
        law_source="個人資料保護法",
        article_number="第 3 條",
        title="當事人個資權利",
        text="當事人就其個人資料依本法規定行使之下列權利,不得預先拋棄或以特約限制之:一、查詢或請求閱覽。二、請求製給複製本。三、請求補充或更正。四、請求停止蒐集、處理或利用。五、請求刪除。",
        keywords=("個資查詢", "刪除個資", "更正資料", "閱覽"),
        scenarios=("想知道公司有哪些我的個資", "想刪除網站上我的個資"),
        application_hint="可向業者書面要求查詢 / 更正 / 刪除;業者不回應可向個資會檢舉。",
    ),
]


def get_all_articles() -> list[Article]:
    return ARTICLES


def make_search_text(article: Article) -> str:
    """組合 title + text + keywords + scenarios + hint 給 BM25 索引。"""
    parts = [article.title, article.text]
    parts.extend(article.keywords)
    parts.extend(article.scenarios)
    parts.append(article.application_hint)
    return " ".join(parts)
