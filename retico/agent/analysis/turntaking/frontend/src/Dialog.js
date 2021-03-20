import DialogAudio from './DialogAudio'
import Turns from './Turns'


export default function Dialog(props) {
  return (
    <div className="dialog">
      <DialogAudio
        interaction={props.interaction}
        wavHeight={100}
        id='dialog'/>
      <Turns interaction={props.interaction}/>
    </div>
  )
};
