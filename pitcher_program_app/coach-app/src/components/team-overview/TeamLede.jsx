import Lede from '../shell/Lede'
import { buildTeamLede } from '../../utils/teamLede'

export default function TeamLede({ roster = [], compliance = { checked_in_today: 0, total: 0, flags: { red: 0, yellow: 0, green: 0 } } }) {
  const { text } = buildTeamLede(roster, compliance)
  return <Lede>{text}</Lede>
}
