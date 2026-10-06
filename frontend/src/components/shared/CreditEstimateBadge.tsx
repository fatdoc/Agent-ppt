import { Coins } from 'lucide-react';

type Operation =
  | 'outline'
  | 'outline_and_descriptions'
  | 'descriptions'
  | 'images'
  | 'image_edit'
  | 'material_image'
  | 'editable_export'
  | 'ppt_to_ppt';

export function estimateCredits(operation: Operation, pageCount: number, referencePageCount = 0, targetPageCount = 0): number {
  const pages = Math.max(1, pageCount || 0);
  const refs = Math.max(1, referencePageCount || 0);
  const targets = Math.max(1, targetPageCount || pageCount || referencePageCount || 0);

  switch (operation) {
    case 'outline':
      return 20 + 3 * pages;
    case 'outline_and_descriptions':
      return 20 + 8 * pages;
    case 'descriptions':
      return 10 + 8 * pages;
    case 'images':
      return 100 * pages;
    case 'image_edit':
      return 120 * pages;
    case 'material_image':
      return 100;
    case 'editable_export':
      return 30 + 80 * pages;
    case 'ppt_to_ppt':
      return 80 + 5 * refs + 15 * targets;
    default:
      return 0;
  }
}

export function CreditEstimateBadge({
  operation,
  pageCount,
  referencePageCount,
  targetPageCount,
  className = '',
}: {
  operation: Operation;
  pageCount: number;
  referencePageCount?: number;
  targetPageCount?: number;
  className?: string;
}) {
  const amount = estimateCredits(operation, pageCount, referencePageCount, targetPageCount);
  if (!amount) return null;

  return (
    <span
      title={`预计消耗 ${amount.toLocaleString()} 积分`}
      className={`inline-flex h-6 items-center gap-1 rounded-full border border-banana/30 bg-banana/10 px-2 text-xs font-bold text-gray-800 dark:border-banana/20 dark:bg-banana/5 dark:text-foreground-primary ${className}`}
    >
      <Coins className="h-3.5 w-3.5 text-banana" />
      <span>{amount.toLocaleString()}</span>
    </span>
  );
}
