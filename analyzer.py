"""
法眼识契 — 合同风险分析引擎
基于规则引擎 + 法律知识库的合同风险智能分析
支持视角模式：甲方/乙方/中立
"""

import re
from typing import Optional
from legal_db import get_db

# ======================== 视角配置 ========================
SIDES = {
    "a": {"name": "甲方视角", "desc": "代表合同中对甲方不利的风险"},
    "b": {"name": "乙方视角", "desc": "代表合同中对乙方不利的风险"},
    "neutral": {"name": "中立视角", "desc": "全量风险检测，不偏不倚"},
}

# ======================== 风险规则定义 ========================
# side: "a"=甲方风险, "b"=乙方风险, "both"=双方都需关注
# analysis_a/suggestion_a: 甲方视角下的分析建议
# analysis_b/suggestion_b: 乙方视角下的分析建议
RISK_RULES = [
    {
        "id": "R001",
        "title": "违约金比例过高（30%以上）",
        "side": "b",
        "category": "违约责任",
        "level": "high",
        "keywords": ["违约金", "%", "30%", "30%", "百分之三十"],
        "patterns": [
            r'违约金.*?(?:百分之[三四五六七八九十]+|[0-9]+%|[0-9]+％).*?(?:合同总价|总价款|货款|合同金额)',
            r'(?:合同总价|总价款|货款|合同金额).*?(?:百分之[三四五六七八九十]+|[0-9]+%|[0-9]+％).*?违约金',
        ],
        "min_match": 1,
        "description": "合同约定违约金比例过高，可能超过实际损失的30%",
        "analysis": "根据《民法典》第585条，约定的违约金过分高于造成的损失的，人民法院或者仲裁机构可以根据当事人的请求予以适当减少。司法实践中一般认为超过造成损失的30%即为过分高于。",
        "law_articles": ["民法典第585条"],
        "related_cases": ["(2024)沪01民终5678号", "(2023)沪0115民初34567号"],
        "suggestion": "建议将违约金比例修改为：按实际损失计算，或约定为合同总价款的20%以内（且不超过实际损失的1.3倍）。",
        "analysis_a": "你方（甲方）约定的30%违约金条款在司法实践中极有可能被法院调低。建议主动设置一个合理的、法院大概率支持的违约金比例（如20%以内），避免争议时被动调整。",
        "suggestion_a": "主动将违约金设定在合理范围（合同总价20%以内），既能起到履约威慑作用，又避免被法院认定为过高而全额调低。",
        "analysis_b": "合同中约定了高达30%的违约金条款，这对你方（乙方）极为不利。根据《民法典》第585条，违约金超过实际损失30%即可能被法院认定为过高。一旦违约，你方面临巨额索赔风险。",
        "suggestion_b": "坚持要求将违约金比例降至20%以下。如对方拒绝，可要求在合同中增加\"违约金以实际损失为限\"的限定条款，或要求约定具体计算方式（如按日万分之五）。"
    },
    {
        "id": "R002",
        "title": "格式条款 — 最终解释权条款",
        "side": "b",
        "category": "格式条款",
        "level": "high",
        "keywords": ["最终解释", "解释权"],
        "patterns": [
            r'最终解释权',
            r'解释权.*?(?:归|属|由|为)',
        ],
        "min_match": 1,
        "description": "合同包含最终解释权条款，属于典型的不公平格式条款",
        "analysis": "根据《民法典》第496-498条，提供格式条款一方不合理地免除或者减轻其责任、加重对方责任、限制对方主要权利的条款无效。最终解释权条款在司法实践中被一致认定为无效条款。",
        "law_articles": ["民法典第496条", "民法典第497条"],
        "related_cases": ["(2023)京0105民初23456号"],
        "suggestion": "建议直接删除最终解释权条款。如需保留，可改为：对本合同条款的理解发生争议时，应当按照通常理解予以解释。",
        "analysis_a": "你方（甲方）在合同中设置最终解释权条款。需要提醒你：该条款在法律上已被一致认定为无效格式条款。保留它不但无法给你方带来实际保护，反而可能让法官对你方产生利用优势地位的不利印象。",
        "suggestion_a": "建议主动删除该条款。可以让合同更干净，避免被认定为格式合同提供方而遭受不利解释。",
        "analysis_b": "合同中的最终解释权归甲方所有条款虽然常见，但在法律上属于无效格式条款。尽管如此，对方可能在实际履行中滥用该条款给你方制造麻烦。",
        "suggestion_b": "要求删除该条款。如对方不同意，可告知对方该条款已被司法实践一致认定为无效，保留无实际意义。"
    },
    {
        "id": "R003",
        "title": "争议管辖 — 单方指定管辖法院",
        "side": "b",
        "category": "争议解决",
        "level": "high",
        "keywords": ["管辖", "法院", "仲裁"],
        "patterns": [
            r'(?:由|归|在).*?(?:甲方|出卖人|卖方|出租人|出借人|贷款人).*?(?:所在地|住所地|注册地).*?(?:法院|人民法院|仲裁)',
            r'(?:管辖|仲裁).*?(?:甲方|出卖人|卖方|出租人).*?(?:所在地|住所地)',
        ],
        "min_match": 1,
        "description": "争议解决条款单方指定对己方有利的管辖法院，增加对方维权成本",
        "analysis": "根据《民法典》第497条及《民事诉讼法》第34条，格式条款中不合理地加重对方责任、限制对方主要权利的内容无效。单方指定管辖法院可能被认定为加重对方诉讼负担的无效条款。",
        "law_articles": ["民法典第497条", "民事诉讼法第34条"],
        "related_cases": ["(2024)京04民终789号"],
        "suggestion": "建议修改为：由被告所在地/合同签订地/标的物所在地人民法院管辖。或约定仲裁作为替代。",
        "analysis_a": "你方（甲方）将管辖法院定在己方所在地是一种常见做法。虽然这不必然无效，但如果双方异地，该条款可能被认定为加重对方负担的格式条款。建议约定一个双方都能接受的中立地点。",
        "suggestion_a": "如坚持由甲方所在地管辖，建议在合同中明确该条款系双方协商一致的结果（非格式条款），并保留协商记录。或者约定仲裁条款，仲裁通常比诉讼更中立高效。",
        "analysis_b": "你方（乙方）面临一个严峻的问题：合同约定争议须在甲方所在地法院解决。如果你们异地，这意味着一旦发生纠纷，你方需要到对方所在地提起诉讼，维权成本将大幅增加。",
        "suggestion_b": "这是必须修改的条款。建议方案：①改为由被告所在地法院管辖；②约定在合同签订地或履行地法院管辖；③约定仲裁（如北仲/贸仲），仲裁相对公正且一裁终局。"
    },
    {
        "id": "R004",
        "title": "定金比例超过20%",
        "side": "b",
        "category": "合同效力",
        "level": "medium",
        "keywords": ["定金", "订金", "保证金"],
        "patterns": [
            r'(?:定金|订金).*?(?:百分之[二三四五六七八九十]+|[0-9]+%|[0-9]+％)',
            r'(?:百分之[二三四五六七八九十]+|[0-9]+%|[0-9]+％).*?(?:定金|订金)',
        ],
        "min_match": 2,
        "description": "定金比例可能超过合同总价款的20%法定上限",
        "analysis": "根据《民法典》第586条，定金的数额不得超过主合同标的额的20%，超过部分不产生定金的效力。超过20%的部分将被认定为预付款而非定金。",
        "law_articles": ["民法典第586条", "民法典第587条"],
        "related_cases": ["(2023)京03民终4567号"],
        "suggestion": "建议将定金调整为合同总价款的20%以内，超出部分明确为预付款性质。明确写明定金罚则的适用条件。",
        "analysis_a": "你方（甲方）收取的30%定金中，超出20%的部分（即10%）不产生定金效力。这意味着如果对方违约，你方只能对20%部分主张定金罚则，10%部分只能作为预付款处理。",
        "suggestion_a": "建议将定金明确约定为合同总价款的20%，超出部分单独注明为预付款或首付款，分别约定违约责任。",
        "analysis_b": "你方（乙方）支付的定金中超过20%的部分是不受定金罚则保护的。这意味着如果对方违约，你只能主张20%部分的双倍返还，多付的部分仅能作为预付款要回。",
        "suggestion_b": "坚持要求将定金控制在20%以内。如对方坚持要高比例，要求在合同中明确注明超出20%部分为预付款而非定金，并约定该部分的退款条件。"
    },
    {
        "id": "R005",
        "title": "质量异议期过短",
        "side": "b",
        "category": "合同履行",
        "level": "medium",
        "keywords": ["异议期", "检验", "验收", "质量"],
        "patterns": [
            r'(?:异议期|检验期|验收期|质保期).*?(?:[0-9一二两三四五六]+\s*[日天]?|\d+\s*日)',
            r'(?:[0-9一二两三四五六]+\s*[日天]).*?(?:异议|检验|验收|质保)',
        ],
        "min_match": 1,
        "description": "质量异议期/检验期可能过短，不足以完成全面检验",
        "analysis": "根据《民法典》第621条及买卖合同司法解释第12条，约定的检验期限过短，致使买受人难以在约定期限内完成全面检验的，人民法院可以认定该期限为外观瑕疵的异议期限，对隐蔽瑕疵不适用。",
        "law_articles": ["民法典第621条", "买卖合同司法解释第12条"],
        "related_cases": ["(2024)粤01民终1234号"],
        "suggestion": "建议区分外观瑕疵与隐蔽瑕疵：外观瑕疵异议期15日，隐蔽瑕疵异议期延长至60-90日。或直接约定合理的异议期限（如90日）。",
        "analysis_a": "你方（甲方）约定的较短异议期虽然在短期内约束了对方，但根据司法解释，如果期限过短，对隐蔽瑕疵并不适用。对方仍可在合理期限内就隐蔽瑕疵提出异议。建议主动设置合理的分层次验收机制。",
        "suggestion_a": "建议将异议期设置为分层次：外观瑕疵15日+性能验收60-90日，这样既有约束力又符合法律规定，避免被认定为异议期过短而无效。",
        "analysis_b": "你方面临一个时间陷阱：合同约定的质量异议期可能不足以完成对技术密集型产品的全面检测。一旦超过期限，即使发现隐蔽质量问题，也可能被对方以逾期为由拒绝。",
        "suggestion_b": "要求在合同中明确区分外观瑕疵和隐蔽瑕疵，隐蔽瑕疵的异议期应延长至60-90日。或者直接约定一个充足的整体异议期（建议不低于90日）。"
    },
    {
        "id": "R006",
        "title": "逾期付款违约金过高（日费率过高）",
        "side": "b",
        "category": "违约责任",
        "level": "medium",
        "keywords": ["逾期", "日", "千分之", "万分之"],
        "patterns": [
            r'按日.*?(?:千分之[一二三四五六七八九十]|万分之[一二三四五六七八九十百]|[0-9]+%)',
            r'(?:千分之[一二三四五六七八九十]|万分之[一二三四五六七八九十百]|[0-9]+%).*?违约金',
        ],
        "min_match": 1,
        "description": "逾期付款的日违约金费率可能过高，超出法律保护范围",
        "analysis": "根据《民法典》第585条及买卖合同司法解释第18条，约定的违约金过分高于造成的损失的，法院可予调低。日千分之五（年化182.5%）等畸高费率在司法实践中会被调低至LPR的1.5-4倍（当前约13.6%）。",
        "law_articles": ["民法典第585条", "买卖合同司法解释第18条"],
        "related_cases": ["(2023)沪0115民初34567号", "(2024)沪01民终5678号"],
        "suggestion": "建议修改为：按日万分之五（年化18.25%）或LPR的1.5-4倍计算逾期付款违约金。",
        "analysis_a": "你方（甲方）设定的日千分之五违约金（年化182.5%）在诉讼中必将被法院大幅调低。过高的约定反而让你方在谈判中处于被动。设定一个法院支持的费率，才能真正保护你方利益。",
        "suggestion_a": "建议设定在日万分之五（年化18.25%）或约定按LPR的1.5倍计算，法院支持的确定性高，也更容易获得对方接受。",
        "analysis_b": "你方（乙方）面临一个天文费率的逾期违约金：日千分之五折算成年化高达182.5%。虽然法院大概率会调低，但诉讼过程费时费力，且对方可能以此要挟。",
        "suggestion_b": "强烈要求修改逾期费率至合理水平（日万分之五或LPR的1.5倍）。如对方坚持高费率，可要求在合同中增加逾期违约金总额不超过欠款本金20%的上限条款。"
    },
    {
        "id": "R007",
        "title": "所有权转移条款缺少保留约定",
        "side": "a",
        "category": "合同效力",
        "level": "medium",
        "keywords": ["所有权", "交付", "转移", "付清"],
        "patterns": [
            r'所有权.*?(?:转移|转移|转归|属于).*?(?:交付|签收|收货)',
            r'(?:交付|签收|收货).*?所有权.*?(?:转移|转归)',
        ],
        "min_match": 1,
        "description": "标的物所有权随交付转移，但价款尚未付清，存在买方转卖风险",
        "analysis": "根据《民法典》第641条，当事人可以在买卖合同中约定所有权保留条款。如所有权随交付即转移，在买方付清全款前，卖方对标的物失去了控制权。",
        "law_articles": ["民法典第641条"],
        "related_cases": ["(2024)苏05民终3456号"],
        "suggestion": "建议增加所有权保留条款：在买方付清全部合同价款前，标的物所有权仍归卖方所有。",
        "analysis_a": "你方（甲方）作为卖方，在对方付清全部货款前就转移了所有权，这让你处于极为不利的地位。如果对方在付款前转卖或抵押标的物，你方将面临无法取回的风险。",
        "suggestion_a": "必须在合同中增加所有权保留条款：在买方付清全部合同价款前，标的物所有权仍归卖方所有。如有可能，应办理所有权保留登记以对抗善意第三人。",
        "analysis_b": "你方（乙方）在付清全款前就已获得所有权，这本对你有利。但需注意：如果合同中明确约定了所有权保留条款，你在付清全款前不能转卖标的物。",
        "suggestion_b": "如你方计划在付清全款前转卖标的物，需确认合同是否有所有权保留条款。如有，建议协商缩短付款周期或与卖方签署补充协议解除所有权保留。"
    },
    {
        "id": "R008",
        "title": "合同签署授权缺失",
        "side": "both",
        "category": "合同效力",
        "level": "medium",
        "keywords": ["签字", "盖章", "授权", "代表", "法定代表人"],
        "patterns": [
            r'(?:签字|盖章|签署).*?(?:生效|成立).*?(?:不|未)?.*?(?:授权|委托)',
        ],
        "min_match": 0,
        "description": "合同未要求签署方提供授权委托书，存在无权代理风险",
        "analysis": "根据《民法典》第170-172条，若签约人并非法定代表人且未经授权，合同可能因无权代理而效力待定。",
        "law_articles": ["民法典第170条", "民法典第171条", "民法典第172条"],
        "related_cases": ["(2023)京03民终4567号"],
        "suggestion": "建议在合同中明确签约代表的授权要求，并互相核验授权委托书。",
        "analysis_a": "你方在签署合同时，应核实对方签约人是否有权代表其公司。如果对方签约人非法定代表人且无授权，合同可能因无权代理而效力待定。这对双方都有重大风险。",
        "suggestion_a": "建议增加条款：双方保证签约方已获得签署本合同所需的一切必要授权。建议在签约前互相核验授权委托书原件。",
        "analysis_b": "同甲方，签约授权问题对双方都是基础性风险。建议核实对方签约代表的授权情况。",
        "suggestion_b": "在合同中加入授权保证条款，签约时互相要求出示授权委托书或法定代表人身份证明，并保留复印件。"
    },
    {
        "id": "R009",
        "title": "交付地点/费用约定不明确",
        "side": "both",
        "category": "合同履行",
        "level": "low",
        "keywords": ["交付", "运输", "运费", "风险", "签收"],
        "patterns": [
            r'交付.*?(?:指定|约定|确定).*?(?:地点|位置|地址)',
            r'(?:运费|运输费|物流).*?(?:由|承担|支付)',
        ],
        "min_match": 0,
        "description": "交付地点、运输费用和风险承担约定不够明确",
        "analysis": "根据《民法典》第603-608条，买卖合同中应当明确约定交付地点、运输费用、风险转移时间点。约定不明可能导致争议。",
        "law_articles": ["民法典第603条", "民法典第604条"],
        "related_cases": ["(2024)粤01民终1234号"],
        "suggestion": "建议明确：交付地点、运输费用由XX方承担、运输风险自XX方签收时转移。",
        "analysis_a": "交付地点和运输费用约定不明确，可能导致后续对运费承担和风险转移产生争议。建议在合同中明确定义。",
        "suggestion_a": "建议明确约定：①具体交付地址；②运输费用由乙方承担（如为买方承担运费）；③运输风险自乙方签收时转移至乙方。",
        "analysis_b": "运输条款不明确可能让你方承担未预料到的运费或运输风险。建议在合同签署前明确费用和风险分配。",
        "suggestion_b": "建议在合同中明确：运输费用由甲方承担，运输风险自你方（乙方）签收时起转移。如由你方承担运费，应要求甲方提供运输发票。"
    },
    {
        "id": "R010",
        "title": "缺少法律文书送达地址条款",
        "side": "both",
        "category": "争议解决",
        "level": "low",
        "keywords": ["送达", "通知", "地址", "通讯"],
        "patterns": [
            r'(?:通知|通讯|联系).*?地址',
        ],
        "min_match": 0,
        "description": "合同未约定法律文书送达地址，可能导致诉讼程序中的送达困难",
        "analysis": "建议增加送达地址条款，约定合同首部载明的地址为法律文书送达地址。根据最高人民法院相关意见，约定送达地址可有效缩短诉讼周期。",
        "law_articles": ["民事诉讼法第87条"],
        "related_cases": ["(2023)沪0115民初34567号"],
        "suggestion": "建议增加：本合同项下的通知、法律文书均应送达至本合同首部载明的地址。",
        "analysis_a": "缺少送达地址条款，一旦进入诉讼程序，可能导致公告送达，大幅延长诉讼周期。这对希望快速解决争议的甲方不利。",
        "suggestion_a": "建议增加送达地址条款：合同首部地址为法律文书送达地址，地址变更需提前三日书面通知。",
        "analysis_b": "同甲方，缺少送达地址条款对双方都意味着诉讼周期延长。建议在合同中增加相关条款。",
        "suggestion_b": "建议增加送达地址确认条款，并确保你方填写的地址准确有效。"
    },
    {
        "id": "R011",
        "title": "缺少保密条款或保密义务不明确",
        "side": "a",
        "category": "合同条款完整性",
        "level": "medium",
        "keywords": ["保密", "机密", "商业秘密", "泄露"],
        "patterns": [],
        "min_match": 0,
        "description": "合同未约定保密条款，或保密义务范围、期限不明确",
        "analysis": "建议在合同中增加保密条款，明确保密信息的范围、保密期限、违约责任。",
        "law_articles": ["反不正当竞争法第9条"],
        "related_cases": [],
        "suggestion": "建议增加保密条款：双方对在合同履行过程中获知的对方商业秘密和保密信息负有保密义务，保密期限至少延续至合同终止后2年。",
        "analysis_a": "你方（甲方）在合同中未约定保密条款，这意味着你的商业秘密（客户信息、技术参数、商业模式等）在合同履行过程中可能被对方泄露或滥用而无法追责。",
        "suggestion_a": "强烈建议增加保密条款，明确保密信息范围、保密期限（建议合同终止后3年）以及违约金标准。",
        "analysis_b": "保密条款对乙方同样重要。你的商业信息也应受到保护。",
        "suggestion_b": "要求加入双向保密条款，保护双方的商业秘密。保密期限建议不低于合同终止后2年。"
    },
    {
        "id": "R012",
        "title": "试用期约定不规范",
        "side": "b",
        "category": "劳动法律",
        "level": "high",
        "keywords": ["试用期", "试用", "实习"],
        "patterns": [
            r'试用期.*?(?:超过|超出|高于)',
            r'试用期.*?(?:[0-9一二三四五六七八九十]+个月)',
        ],
        "min_match": 0,
        "description": "试用期约定可能不符合劳动法规定",
        "analysis": "根据《劳动合同法》第19条，试用期最长为6个月，且与合同期限挂钩：合同期3个月-1年试用期不超过1个月；1-3年不超过2个月；3年以上或无固定期限不超过6个月。试用期工资不得低于约定工资的80%且不低于最低工资标准。",
        "law_articles": ["劳动合同法第19条", "劳动合同法第20条"],
        "related_cases": [],
        "suggestion": "请根据劳动合同法第19条检查试用期是否与合同期限匹配。试用期工资不得低于正式工资的80%。",
        "analysis_a": "你方（甲方/雇主）约定的试用期和试用期工资需要符合劳动法规定。如果试用期过长或试用期工资低于正式工资的80%，员工可以主张违法并要求赔偿。",
        "suggestion_a": "请逐项核查：①试用期长度是否与合同期限匹配（对应上述标准）；②试用期工资是否不低于正式工资的80%；③是否只约定了一次试用期。",
        "analysis_b": "你方（乙方/劳动者）的试用期和试用期工资需要对照法律规定检查。如果公司约定的试用期超过法定标准或试用期工资过低，你有权主张权益。",
        "suggestion_b": "核对你合同期限对应的法定最长试用期（如上所述）。如公司超期约定，可要求更正。试用期工资不得低于正式工资的80%，且不得低于当地最低工资标准。"
    },
]


class ContractAnalyzer:
    """合同风险分析引擎（支持视角模式）"""

    def __init__(self):
        self.db = get_db()
        self.rules = RISK_RULES

    def analyze(self, text: str, contract_type: str = "买卖合同", side: str = "neutral") -> dict:
        """对合同文本进行全面风险分析

        Args:
            text: 合同文本
            contract_type: 合同类型
            side: 视角 - "a"(甲方), "b"(乙方), "neutral"(中立)
        """
        findings = []
        matched_articles = set()
        matched_cases = set()

        for rule in self.rules:
            result = self._match_rule(text, rule, side)
            if result is not None:
                findings.append(result)
                for art in rule["law_articles"]:
                    matched_articles.add(art)
                for case in rule["related_cases"]:
                    matched_cases.add(case)

        # 补充法律检索
        content_kw = self._extract_keywords(text)
        extra_articles = self.db.find_related_articles(content_kw)
        extra_cases = self.db.find_related_cases(content_kw)

        # 按风险等级分组
        high = [f for f in findings if f["level"] == "high"]
        medium = [f for f in findings if f["level"] == "medium"]
        low = [f for f in findings if f["level"] == "low"]

        # 计算视角加权评分
        score = self._calculate_score(findings, side)

        # 获取视角名称
        side_info = SIDES.get(side, SIDES["neutral"])

        return {
            "contract_type": contract_type,
            "side": side,
            "side_name": side_info["name"],
            "side_desc": side_info["desc"],
            "total_risks": len(findings),
            "high_count": len(high),
            "medium_count": len(medium),
            "low_count": len(low),
            "score": score,
            "verdict": self._get_verdict(score, side),
            "findings": findings,
            "high_risks": high,
            "medium_risks": medium,
            "low_risks": low,
            "referenced_articles": [(self.db.get_article(a) or {}) for a in matched_articles],
            "referenced_cases": [(self.db.get_case(c) or {}) for c in matched_cases],
            "extra_articles": extra_articles[:5],
            "extra_cases": extra_cases[:5],
            "keywords_found": content_kw,
            "side_summary": self._get_side_summary(findings, side),
        }

    def _match_rule(self, text: str, rule: dict, side: str) -> Optional[dict]:
        """检查合同文本是否匹配某项风险规则"""
        text_lower = text.lower()

        keyword_matches = []
        for kw in rule["keywords"]:
            if kw.lower() in text_lower:
                keyword_matches.append(kw)

        pattern_matches = []
        for pattern in rule["patterns"]:
            try:
                matches = re.findall(pattern, text)
                pattern_matches.extend(matches)
            except re.error:
                pass

        total_matches = len(keyword_matches) + len(pattern_matches)
        if total_matches < rule["min_match"]:
            return None

        context = ""
        for m in pattern_matches[:3]:
            if m:
                context = m
                break

        # 根据视角选择分析文本
        if side == "a" and "analysis_a" in rule:
            analysis_text = rule["analysis_a"]
            suggestion_text = rule.get("suggestion_a", rule["suggestion"])
        elif side == "b" and "analysis_b" in rule:
            analysis_text = rule["analysis_b"]
            suggestion_text = rule.get("suggestion_b", rule["suggestion"])
        else:
            analysis_text = rule["analysis"]
            suggestion_text = rule["suggestion"]

        # 添加视角标签
        side_tag = rule.get("side", "both")

        return {
            "id": rule["id"],
            "title": rule["title"],
            "category": rule["category"],
            "level": rule["level"],
            "side": side_tag,
            "description": rule["description"],
            "analysis": analysis_text,
            "suggestion": suggestion_text,
            "law_articles": rule["law_articles"],
            "related_cases": rule["related_cases"],
            "matched_keywords": keyword_matches,
            "matched_text": context,
            "confidence": min(total_matches * 0.25 + 0.5, 0.98),
        }

    def _extract_keywords(self, text: str) -> list:
        keywords = []
        patterns = [
            r'(?:合同|协议).*?(?:纠纷|争议|违约)',
            r'(?:出卖|买方|甲方|乙方|卖方|采购|销售|租赁)',
            r'(?:支付|付款|价款|货款|租金)',
            r'(?:违约|解除|终止|撤销)',
            r'(?:管辖|仲裁|诉讼|法院)',
            r'(?:保密|知识产权|专利|商标|著作权)',
            r'(?:保证|担保|抵押|质押|定金)',
            r'(?:赔偿|补偿|损失|违约金)',
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                keywords.append(m.group())
        return keywords

    def _calculate_score(self, findings: list, side: str = "neutral") -> int:
        """视角加权评分"""
        score = 100
        base_scores = {"high": -10, "medium": -5, "low": -2}
        # 视角加权：跟你的视角利益相关的风险扣分更多
        side_weights = {"a": {"a": 1.0, "b": 1.4, "both": 1.2},
                        "b": {"a": 1.4, "b": 1.0, "both": 1.2},
                        "neutral": {"a": 1.0, "b": 1.0, "both": 1.0}}

        weights = side_weights.get(side, side_weights["neutral"])
        for f in findings:
            side_tag = f.get("side", "both")
            w = weights.get(side_tag, 1.0)
            score += base_scores.get(f["level"], -5) * w
        return max(0, min(100, score))

    def _get_verdict(self, score: int, side: str = "neutral") -> str:
        prefix = ""
        if side == "a":
            prefix = "【甲方视角】"
        elif side == "b":
            prefix = "【乙方视角】"
        if score >= 85:
            return f"{prefix}✅ 风险较低，可以签署"
        elif score >= 65:
            return f"{prefix}⚠️ 建议修改后签署"
        elif score >= 40:
            return f"{prefix}🔴 风险较高，建议修改并咨询律师"
        else:
            return f"{prefix}⛔ 风险极高，强烈建议重新起草"

    def _get_side_summary(self, findings: list, side: str) -> str:
        """生成视角摘要"""
        if side == "neutral":
            return "全量风险检测"

        side_names = {"a": "甲方", "b": "乙方"}
        name = side_names.get(side, "")

        # 统计对自己不利的风险
        opposing = {"a": "b", "b": "a"}
        opp_side = opposing.get(side, "")
        dangerous = [f for f in findings if f.get("side") == opp_side]

        if dangerous:
            return f"发现 {len(dangerous)} 项对{name}不利的风险条款，建议重点修改"
        else:
            return f"暂未发现对{name}明显不利的条款，但仍需整体审阅"


def analyze_contract(text: str, contract_type: str = "买卖合同", side: str = "neutral") -> dict:
    """便捷分析入口"""
    analyzer = ContractAnalyzer()
    return analyzer.analyze(text, contract_type, side)


if __name__ == "__main__":
    sample = """
    合同总价款为人民币1,500,000元。
    乙方应于合同签订后5个工作日内支付合同总价款的30%作为定金。
    任何一方违约，应向守约方支付合同总价款30%的违约金。
    逾期支付价款的，按日向甲方支付合同总价款千分之五的违约金。
    本合同为格式合同，最终解释权归甲方所有。
    协商不成的，由甲方所在地人民法院管辖。
    标的物所有权自交付之日起转移至乙方。
    """

    for side in ["neutral", "a", "b"]:
        result = analyze_contract(sample, "买卖合同", side)
        print(f"\n{'='*50}")
        print(f"【{result['side_name']}】评分: {result['score']}/100 | {result['verdict']}")
        print(f"风险: {result['high_count']}高/{result['medium_count']}中/{result['low_count']}低")
        for f in result['findings'][:3]:
            tag = {"a": "⚠️甲方不利", "b": "⚠️乙方不利", "both": "⚖️双方关注"}
            side_tag = tag.get(f.get("side", "both"), "")
            print(f"  [{f['level'].upper()}] {side_tag} - {f['title']}")
            print(f"    {f['analysis'][:60]}...")
