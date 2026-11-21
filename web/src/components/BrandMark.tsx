import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';

export function BrandMark({ size = 40 }: { size?: number }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <Box
        aria-hidden
        sx={{
          width: size,
          height: size,
          borderRadius: 2,
          bgcolor: 'primary.main',
          color: 'primary.contrastText',
          display: 'grid',
          placeItems: 'center',
          fontWeight: 700,
          fontSize: size * 0.55,
        }}
      >
        س
      </Box>
      <Typography component="span" sx={{ fontWeight: 700, fontSize: size * 0.5 }}>
        سِجلّ
      </Typography>
    </Box>
  );
}
