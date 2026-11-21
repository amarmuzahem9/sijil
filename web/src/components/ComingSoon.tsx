import HourglassEmptyOutlined from '@mui/icons-material/HourglassEmptyOutlined';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';

/** Empty placeholder for pages built in later features. */
export function ComingSoon({ title }: { title: string }) {
  return (
    <>
      <Typography component="h1" variant="h5" sx={{ fontWeight: 700, mb: 2 }}>
        {title}
      </Typography>
      <Paper
        variant="outlined"
        sx={{ p: 4, textAlign: 'center', color: 'text.secondary', borderStyle: 'dashed' }}
      >
        <HourglassEmptyOutlined sx={{ fontSize: 40, mb: 1 }} />
        <Typography>قريباً</Typography>
      </Paper>
    </>
  );
}
