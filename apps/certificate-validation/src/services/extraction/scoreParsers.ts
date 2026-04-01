export function parseIeltsOverall(text: string): number | null {
  const m =
    text.match(/overall\s*band\s*score[^0-9]*([0-9](?:\.[05])?)/i) ||
    text.match(/\bb\s*and\s*score[^0-9]*([0-9](?:\.[05])?)/i) ||
    text.match(/\boverall[^0-9]*([0-9](?:\.[05])?)/i);
  return m ? Number(m[1]) : null;
}

export function parseToeflScore(text: string): number | null {
  const m = text.match(/\btotal\s*score[^0-9]*([0-9]{2,3})\b/i) || text.match(/\btoefl[^0-9]*([0-9]{2,3})\b/i);
  return m ? Number(m[1]) : null;
}

export function parseEntScore(text: string): number | null {
  const m = text.match(/(?:ент|ниш|балл|score)[^0-9]{0,20}([0-9]{2,3})/i);
  return m ? Number(m[1]) : null;
}
