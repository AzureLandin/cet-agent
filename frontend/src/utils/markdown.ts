import { marked } from "marked";
import DOMPurify from "dompurify";

marked.setOptions({
  breaks: true,
  gfm: true,
});

const TOOL_MARKUP_RE =
  /<tool_call\b[\s\S]*?(?:<\/tool_call>|$)|<function=[\s\S]*?(?:<\/function>|$)|<\|tool_call\|>[\s\S]*?(?:<\|\/tool_call\|>|$)|<\|tool_calls_section_begin\|>[\s\S]*?(?:<\|tool_calls_section_end\|>|$)/gi;

export function stripToolMarkup(text: string): string {
  if (!text) return "";
  return text.replace(TOOL_MARKUP_RE, "").trim();
}

export function renderSanitizedMarkdown(text: string): string {
  const cleaned = stripToolMarkup(text);
  if (!cleaned) return "";
  const rawHtml = marked.parse(cleaned, { async: false }) as string;
  return DOMPurify.sanitize(rawHtml);
}
