import Lede from './Lede'

export default function EditorialState({ type, copy, retry }) {
  return (
    <div className="space-y-3">
      {type === 'loading' && (
        <div
          data-testid="editorial-skeleton"
          className="h-4 w-48 bg-cream-dark/60 rounded-[3px] animate-pulse"
        />
      )}
      <Lede>{copy}</Lede>
      {type === 'error' && retry && (
        <button
          type="button"
          onClick={retry}
          className="font-ui text-body-sm font-semibold text-maroon hover:text-maroon-ink underline underline-offset-2"
        >
          Try again
        </button>
      )}
    </div>
  )
}
