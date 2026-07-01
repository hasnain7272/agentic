import { useState } from 'react';
import { Check, Copy, ExternalLink, Terminal } from 'lucide-react';

interface CopyButtonProps {
  text: string;
}

function CopyButton({ text }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy: ', err);
    }
  };

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1 rounded bg-slate-800/80 px-2 py-1 text-[10px] font-medium text-slate-400 transition hover:bg-slate-700 hover:text-slate-200"
    >
      {copied ? (
        <>
          <Check className="h-3 w-3 text-emerald-400" />
          <span className="text-emerald-400">Copied!</span>
        </>
      ) : (
        <>
          <Copy className="h-3 w-3" />
          <span>Copy</span>
        </>
      )}
    </button>
  );
}

// Simple highlighter helper
function highlightCode(code: string, lang: string) {
  if (!code) return code;
  // Basic token coloring via HTML elements for popular languages
  const escaped = code
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  if (lang === 'python' || lang === 'py') {
    return escaped
      .replace(/\b(def|class|return|if|elif|else|for|in|while|try|except|import|from|as|with|lambda|and|or|not|is|None|True|False)\b/g, '<span class="text-pink-400 font-semibold">$1</span>')
      .replace(/(["'])(.*?)\1/g, '<span class="text-emerald-400">"$2"</span>')
      .replace(/\b(print|len|range|str|int|float|dict|list|set|tuple|getattr|setattr|hasattr)\b/g, '<span class="text-cyan-400">$1</span>')
      .replace(/(#.*)$/gm, '<span class="text-slate-500">$1</span>');
  }

  if (lang === 'javascript' || lang === 'typescript' || lang === 'js' || lang === 'ts' || lang === 'jsx' || lang === 'tsx') {
    return escaped
      .replace(/\b(const|let|var|function|return|if|else|for|while|import|export|from|default|class|extends|new|this|async|await|try|catch|throw|typeof|interface|type|public|private)\b/g, '<span class="text-pink-400 font-semibold">$1</span>')
      .replace(/(["'`])(.*?)\1/g, '<span class="text-emerald-400">"$2"</span>')
      .replace(/\b(console|log|error|warn|window|document|process|require|module)\b/g, '<span class="text-cyan-400">$1</span>')
      .replace(/(\/\/.*)$/gm, '<span class="text-slate-500">$1</span>');
  }

  if (lang === 'bash' || lang === 'shell' || lang === 'sh' || lang === 'powershell' || lang === 'ps1') {
    return escaped
      .replace(/\b(cd|ls|mkdir|rm|cp|mv|git|npm|pip|python|cargo|node|docker|kubectl|cat|grep|echo|exit)\b/g, '<span class="text-cyan-400 font-semibold">$1</span>')
      .replace(/(["'])(.*?)\1/g, '<span class="text-emerald-400">"$2"</span>')
      .replace(/(#.*)$/gm, '<span class="text-slate-500">$1</span>');
  }

  return escaped;
}

export function renderContent(content: string, sessionId?: string) {
  if (!content) return null;

  // 1. Detect absolute image paths (Tool Artifacts)
  const imageRegex = /([a-zA-Z]:\\[^*|"<>?\n]+\.(?:png|jpg|jpeg|webp|gif))/gi;
  
  // 2. Detect "Attached: filename.ext" (User Uploads)
  const attachmentRegex = /Attached: ([^\n]+\.(?:png|jpg|jpeg|webp|gif|mp4|mov|webm))/gi;

  const combinedRegex = new RegExp(`(${imageRegex.source}|${attachmentRegex.source})`, 'gi');

  // Split by code blocks first
  const codeBlockRegex = /```(\w*)\n([\s\S]*?)\n```/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match;

  while ((match = codeBlockRegex.exec(content)) !== null) {
    const textBefore = content.substring(lastIndex, match.index);
    if (textBefore) {
      parts.push(renderTextAndAttachments(textBefore, combinedRegex, imageRegex, sessionId));
    }

    const language = match[1] || 'code';
    const code = match[2];

    parts.push(
      <div key={`code-${match.index}`} className="my-4 overflow-hidden rounded-xl border border-slate-800 bg-slate-950/90 shadow-lg">
        <div className="flex items-center justify-between bg-slate-900/80 px-4 py-2 text-xs border-b border-slate-800">
          <div className="flex items-center gap-1.5 font-mono text-[11px] text-slate-400">
            <Terminal className="h-3.5 w-3.5 text-cyan-400" />
            <span className="font-semibold">{language.toUpperCase()}</span>
          </div>
          <CopyButton text={code} />
        </div>
        <pre className="overflow-x-auto p-4 font-mono text-xs leading-relaxed text-slate-300">
          <code
            dangerouslySetInnerHTML={{ __html: highlightCode(code, language) }}
          />
        </pre>
      </div>
    );

    lastIndex = codeBlockRegex.lastIndex;
  }

  const textRemaining = content.substring(lastIndex);
  if (textRemaining) {
    parts.push(renderTextAndAttachments(textRemaining, combinedRegex, imageRegex, sessionId));
  }

  return <div className="space-y-1.5">{parts}</div>;
}

function renderTextAndAttachments(
  text: string,
  combinedRegex: RegExp,
  imageRegex: RegExp,
  sessionId?: string
): React.ReactNode {
  const parts = text.split(combinedRegex);
  return parts.map((part, i) => {
    if (!part) return null;

    // Check for absolute path artifact
    if (part.match(imageRegex)) {
      return (
        <div key={i} className="my-3 overflow-hidden rounded-xl border border-slate-800/80 bg-slate-950/50 shadow-2xl">
          <img 
            src={`/api/v1/workspace/artifacts?path=${encodeURIComponent(part)}`} 
            alt="Tool Artifact" 
            className="max-h-96 w-full object-contain"
          />
          <div className="bg-slate-900/60 px-3 py-1.5 text-[10px] font-mono text-slate-500 truncate">
            {part}
          </div>
        </div>
      );
    }

    // Check for "Attached: filename.ext"
    const attachmentMatch = part.match(/Attached: ([^\n]+\.(?:png|jpg|jpeg|webp|gif|mp4|mov|webm))/i);
    if (attachmentMatch && sessionId) {
      const filename = attachmentMatch[1];
      const isVideo = /\.(mp4|mov|webm)$/i.test(filename);
      const url = `/api/v1/workspace/sessions/${sessionId}/file/${encodeURIComponent(filename)}`;

      return (
        <div key={i} className="my-3 overflow-hidden rounded-xl border border-cyan-500/20 bg-slate-950/50 shadow-xl">
          {isVideo ? (
            <video src={url} controls className="max-h-96 w-full" />
          ) : (
            <img src={url} alt={filename} className="max-h-96 w-full object-contain" />
          )}
          <div className="bg-cyan-500/5 px-3 py-1.5 text-[10px] font-medium text-cyan-400/80 truncate flex items-center gap-1.5 border-t border-cyan-500/10">
            <div className="h-1.5 w-1.5 rounded-full bg-cyan-500" />
            {filename}
          </div>
        </div>
      );
    }

    // Parse Markdown Inline Elements and Blocks
    return <div key={i} className="prose-slate max-w-none text-slate-300">{parseMarkdownBlocks(part)}</div>;
  });
}

// Parses block elements like bullet lists, ordered lists, and paragraphs
function parseMarkdownBlocks(text: string): React.ReactNode[] {
  const lines = text.split('\n');
  const blocks: React.ReactNode[] = [];
  let currentListItems: React.ReactNode[] = [];
  let currentListType: 'ul' | 'ol' | null = null;
  let blockKey = 0;

  const pushList = () => {
    if (currentListItems.length > 0 && currentListType) {
      const ListTag = currentListType;
      const listClass = currentListType === 'ul' 
        ? 'list-disc pl-5 my-2 space-y-1 text-slate-300 marker:text-cyan-500' 
        : 'list-decimal pl-5 my-2 space-y-1 text-slate-300 marker:text-cyan-500';
      blocks.push(
        <ListTag key={`list-${blockKey++}`} className={listClass}>
          {currentListItems}
        </ListTag>
      );
      currentListItems = [];
      currentListType = null;
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Bullet List Match
    const ulMatch = line.match(/^(\s*)[-*+]\s+(.*)/);
    if (ulMatch) {
      if (currentListType !== 'ul') {
        pushList();
        currentListType = 'ul';
      }
      currentListItems.push(
        <li key={`li-${i}`} className="text-sm">
          {parseInlineMarkdown(ulMatch[2])}
        </li>
      );
      continue;
    }

    // Ordered List Match
    const olMatch = line.match(/^(\s*)\d+\.\s+(.*)/);
    if (olMatch) {
      if (currentListType !== 'ol') {
        pushList();
        currentListType = 'ol';
      }
      currentListItems.push(
        <li key={`li-${i}`} className="text-sm">
          {parseInlineMarkdown(olMatch[2])}
        </li>
      );
      continue;
    }

    // Header Match (e.g. # Header)
    const headerMatch = line.match(/^(#{1,6})\s+(.*)/);
    if (headerMatch) {
      pushList();
      const level = headerMatch[1].length;
      const headerText = headerMatch[2];
      const HeaderTag = `h${level}` as keyof JSX.IntrinsicElements;
      
      const headerClasses: Record<number, string> = {
        1: 'text-lg font-bold text-white mt-4 mb-2 border-b border-slate-800 pb-1.5',
        2: 'text-base font-bold text-white mt-4 mb-2',
        3: 'text-sm font-semibold text-slate-100 mt-3 mb-1.5',
      };
      
      blocks.push(
        <HeaderTag key={`h-${i}`} className={headerClasses[level] || 'text-sm font-semibold text-slate-200 mt-2 mb-1'}>
          {parseInlineMarkdown(headerText)}
        </HeaderTag>
      );
      continue;
    }

    // Horizontal Rule
    if (line.match(/^---$/)) {
      pushList();
      blocks.push(<hr key={`hr-${i}`} className="my-4 border-slate-800/80" />);
      continue;
    }

    // Paragraph
    if (line.trim() === '') {
      pushList();
      continue;
    }

    // Regular text line
    pushList();
    blocks.push(
      <p key={`p-${i}`} className="text-sm leading-relaxed my-1.5 text-slate-300">
        {parseInlineMarkdown(line)}
      </p>
    );
  }

  pushList();
  return blocks;
}

// Parses inline elements: Bold, Italic, Code, Links
function parseInlineMarkdown(text: string): React.ReactNode {
  // Regexes
  const boldRegex = /\*\*([^*]+)\*\*/g;
  const italicRegex = /\*([^*]+)\*/g;
  const codeRegex = /`([^`]+)`/g;
  const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;

  // Let's tokenise the string to parse multiple formatting correctly
  let elements: React.ReactNode[] = [text];

  const applyRegex = (regex: RegExp, formatter: (match: string, p1: string, p2?: string) => React.ReactNode) => {
    elements = elements.flatMap((el) => {
      if (typeof el !== 'string') return [el];
      
      const parts = [];
      let lastIdx = 0;
      let m;
      regex.lastIndex = 0; // reset
      
      while ((m = regex.exec(el)) !== null) {
        const textBefore = el.substring(lastIdx, m.index);
        if (textBefore) parts.push(textBefore);
        
        parts.push(formatter(m[0], m[1], m[2]));
        lastIdx = regex.lastIndex;
      }
      
      const textRemaining = el.substring(lastIdx);
      if (textRemaining) parts.push(textRemaining);
      
      return parts;
    });
  };

  // Bold
  applyRegex(boldRegex, (_, content) => <strong className="font-semibold text-white">{content}</strong>);
  // Italic
  applyRegex(italicRegex, (_, content) => <em className="italic text-slate-200">{content}</em>);
  // Inline Code
  applyRegex(codeRegex, (_, content) => (
    <code className="rounded bg-slate-950/80 border border-slate-800/60 px-1.5 py-0.5 font-mono text-[0.85em] text-cyan-400">
      {content}
    </code>
  ));
  // Links
  applyRegex(linkRegex, (_, label, url) => (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-0.5 text-cyan-400 hover:text-cyan-300 underline font-medium"
    >
      {label}
      <ExternalLink className="h-2.5 w-2.5 opacity-65" />
    </a>
  ));

  return <>{elements}</>;
}
