import DialogAudio from './DialogAudio'
import Turns from './Turns'


export default function Dialog(props) {

  let style = {'background': '#222222', 'color': '##eaeaea'};
  return (
    <div style={style}>
      <DialogAudio
        interaction={props.interaction}
        wavHeight={200}
        id='dialog'/>
      <Turns interaction={props.interaction}/>
    </div>
  )
};
