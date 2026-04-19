import { useCoachAuth } from '../../hooks/useCoachAuth'

export default function TeamBrand() {
  const { coach } = useCoachAuth()
  const teamName = coach?.team_name || 'Dashboard'
  const coachName = coach?.coach_name || ''
  return (
    <div className="px-4 pt-5 pb-4 border-b border-cream-dark">
      <h1 className="font-serif font-bold text-h2 text-maroon leading-tight">{teamName}</h1>
      {coachName && (
        <p className="font-ui text-meta text-muted mt-0.5 leading-tight">{coachName}</p>
      )}
    </div>
  )
}
