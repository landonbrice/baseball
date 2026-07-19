import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from './card';
import { Button } from './button';
import { FlagPill } from './flag-pill';

export default {
  title: 'Primitives/Card',
  component: Card,
  parameters: { layout: 'centered' },
};

export const Basic = {
  render: () => (
    <Card className="w-80">
      <CardHeader>
        <CardTitle className="text-lg">Today · Bullpen</CardTitle>
        <CardDescription>15 pitches · 70% intent · FB/CH mix</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-foreground">
          Light catch play, then a controlled pen. Stop if anything sharpens.
        </p>
      </CardContent>
      <CardFooter className="gap-2">
        <Button size="sm">Start</Button>
        <Button size="sm" variant="ghost">
          Adjust
        </Button>
      </CardFooter>
    </Card>
  ),
};

export const WithFlag = {
  render: () => (
    <Card className="w-80">
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-lg">Sample Pitcher</CardTitle>
          <FlagPill level="yellow" />
        </div>
        <CardDescription>Reliever (short) · sample readiness note</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">AF 7d · 6.2 · trending flat</p>
      </CardContent>
    </Card>
  ),
};
