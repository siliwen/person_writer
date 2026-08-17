const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
  LevelFormat,
} = require("docx");

const PURPLE = "534AB7";
const LIGHT = "EDEAF7";
const GREY = "F2F0EA";

const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };

function cell(text, { bold = false, fill = null, width, align = AlignmentType.LEFT } = {}) {
  return new TableCell({
    borders,
    width: width ? { size: width, type: WidthType.DXA } : undefined,
    shading: fill ? { fill, type: ShadingType.CLEAR } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ alignment: align, children: [new TextRun({ text, bold, font: "Arial", size: 21 })] })],
  });
}

function table(headers, rows, widths) {
  const headerRow = new TableRow({
    children: headers.map((h, i) => cell(h, { bold: true, fill: PURPLE, align: AlignmentType.CENTER, width: widths[i] })),
  });
  const body = rows.map((r) =>
    new TableRow({
      children: r.map((c, i) => cell(String(c), { fill: i === 0 ? LIGHT : null, align: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER, width: widths[i] })),
    })
  );
  return new Table({
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: widths,
    rows: [headerRow, ...body],
  });
}

function h1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)] });
}
function h2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(text)] });
}
function p(text, opts = {}) {
  return new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text, size: 22, font: "Arial", ...opts })] });
}
function bullet(text) {
  return new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 60 }, children: [new TextRun({ text, size: 22, font: "Arial" })] });
}

const doc = new Document({
  numbering: {
    config: [{ reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] }],
  },
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 32, bold: true, color: PURPLE, font: "Arial" }, paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 26, bold: true, font: "Arial" }, paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 1 } },
    ],
  },
  sections: [{
    properties: {
      page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } },
    },
    children: [
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new TextRun({ text: "墨小小 · 用量与额度（积分）设计文档", bold: true, size: 40, color: PURPLE, font: "Arial" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 }, children: [new TextRun({ text: "个人风格写作 Agent SaaS · v1 草案", size: 22, color: "666666", font: "Arial" })] }),

      h1("1. 背景与目标"),
      p("墨小小基于大模型（当前为 Qwen3.7-Plus，风格分析与文章生成共用同一模型）为用户生成具有个人风格的散文、小说、诗歌等。由于模型调用存在真实成本，且不同用户需要差异化的功能与用量，需要一套「用量额度 + 用户等级」体系，实现："),
      bullet("对用户：用量透明、按能力付费、长文更划算；"),
      bullet("对平台：限制单用户资源消耗、按等级控制功能权限、保证商业化毛利；"),
      bullet("对工程：额度与具体模型解耦，便于后续换模型或做促销。"),

      h1("2. 积分定位与成本模型"),
      p("积分为「用户侧用量配额单位」，不直接等于人民币。目的是与具体模型解耦。真实成本按每次调用的 input/output token 实时计算，仅用于平台内部核算，不展示给用户。"),
      table(
        ["项目", "取值", "说明"],
        [
          ["模型", "Qwen3.7-Plus", "风格分析 + 文章生成 同一模型"],
          ["输入单价（≤256k）", "¥1.6 / M tokens", "截图限时 8 折价"],
          ["输出单价（≤256k）", "¥6.4 / M tokens", "截图限时 8 折价"],
          ["每汉字 ≈ tokens", "1.5", "中文经验值，用于估算输出 token"],
          ["文章基础输入 tokens", "约 1500", "风格档案(~1000) + 写作要求(~500)"],
          ["平均单积分成本", "¥0.0043", "按 2000字中篇测算：输入1500+输出3000 tokens ≈ ¥0.0216 / 5 积分"],
        ],
        [2400, 2400, 4560]
      ),

      h1("3. 各操作花费积分设计"),
      h2("3.1 文章生成（按长度分档，长文享折扣）"),
      p("按输出字数分档计费，不是严格线性比例：前 1000 字单价最高，越长单位价格越低，引导深度创作。锚点由产品设定：1000字=3分、2000字=5分、3000字=8分。"),
      table(
        ["长度档（字）", "消耗积分", "每千字平均积分", "说明"],
        [
          ["≤1000", "3", "3.00", "基础档，单价最高"],
          ["≤2000", "5", "2.50", "折扣档，单位比 1000 字更低"],
          ["≤3000", "8", "2.67", "锚点：越长单位价越低"],
          ["≤4000", "11", "2.75", "之后每千字约 +3 分"],
          ["≤5000", "14", "2.80", ""],
          ["≤8000", "22", "2.75", "长文创作场景"],
          ["≤10000", "29", "2.90", "上限，超出联系商务"],
        ],
        [2000, 1800, 2400, 3160]
      ),
      h2("3.2 其他操作（固定积分）"),
      table(
        ["操作", "消耗积分", "说明"],
        [
          ["风格分析", "2", "上传作品诊断六维风格，一次性动作"],
          ["段落重写", "1", "每次重写消耗，与长度无关"],
          ["风格档案编辑", "0", "免费，不计入额度"],
          ["文章保存 / 下载", "0", "免费；仅按等级开放功能权限"],
        ],
        [3200, 2000, 4160]
      ),

      h1("4. 用户等级与套餐"),
      p("采用「包月订阅」模式：每级套餐含固定月积分 + 功能/数量权限。"),
      table(
        ["等级", "月费", "月积分", "风格上限", "作品上限", "下载docx", "段落重写"],
        [
          ["免费版", "¥0", "10", "2", "3", "否", "否"],
          ["基础版", "¥19", "60", "10", "20", "是", "是"],
          ["专业版", "¥49", "200", "30", "100", "是", "是"],
          ["团队版", "¥199", "1000", "不限", "不限", "是", "是"],
        ],
        [1500, 1300, 1500, 1500, 1500, 1300, 1300]
      ),
      p("权限补充：免费版仅可生成 ≤2000 字内容，不支持下载与重写；付费档开放下载、重写与长文；团队版额外含成员管理、共享风格与优先队列。", { italics: true, size: 20, color: "666666" }),

      h1("5. 盈亏测算"),
      p("以专业版（¥49/月，200 积分）为例，按平均单积分成本 ¥0.0043 测算不同使用率下的真实利润："),
      table(
        ["使用率", "实际消耗积分", "实际成本(¥)", "月收入(¥)", "毛利(¥)", "毛利率"],
        [
          ["20%", "40", "0.17", "49", "48.83", "98.0%"],
          ["50%", "100", "0.43", "49", "48.57", "94.9%"],
          ["100%", "200", "0.86", "49", "48.14", "89.8%"],
        ],
        [1500, 2100, 1800, 1800, 1800, 1800]
      ),
      p("即便用户 100% 用满额度，各档毛利率仍约 98%（大模型成本极低）。实际平均使用率通常 20%~50%，真实毛利更高，商业化空间充足。", { size: 20, color: "666666" }),

      h1("6. 后端实施方案"),
      bullet("User 表新增：tier、monthly_quota、used_quota、quota_resets_at。"),
      bullet("UsageRecord 表：operation_type、input_tokens、output_tokens、points_consumed、cost_cny、model、created_at。"),
      bullet("生成 / 分析前校验剩余额度（points ≤ remaining），不足返回 402/403 友好提示。"),
      bullet("quota_resets_at 到期自动重置 used_quota = 0。"),
      bullet("前端在写作页/设置页展示「本月剩余积分」与「本次消耗积分」。"),

      h1("7. 待确认事项"),
      bullet("免费版 10 积分是否合适（约 3 篇短文或 1 篇长文）？"),
      bullet("文章长度分档积分是否采用上文锚点（1000/2000/3000 = 3/5/8）？"),
      bullet("是否需要引入「积分包」或「按量付费」作为订阅之外的补充？"),
      bullet("是否现在落库实现（User + UsageRecord + 额度校验中间件）？"),
    ],
  }],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync("D:/AI_talk/personal_writing_agent_saas/outputs/墨小小_用量额度设计文档.docx", buffer);
  console.log("docx written:", buffer.length, "bytes");
});
