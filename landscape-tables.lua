-- Wrap tables with 5+ columns in landscape environment
function Table(el)
  local cols = #el.colspecs
  if cols >= 5 then
    return {
      pandoc.RawBlock('latex', '\\begin{landscape}'),
      el,
      pandoc.RawBlock('latex', '\\end{landscape}')
    }
  end
  return el
end
