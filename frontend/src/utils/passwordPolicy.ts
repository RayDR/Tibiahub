export const isValidPassword = (password: string): boolean =>
  password.length >= 8
  && password.length <= 128
  && /\p{L}/u.test(password)
  && /\p{Nd}/u.test(password);
