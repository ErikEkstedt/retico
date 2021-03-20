# Experiment

1. Make sure Jack is running
2. Add audio modules: `./prepare_zoom_audio.sh`
3. Start zoom
4. `run_experiment.py --root ~/Experiments --experiment experiment.json -n 0 -i 0`
5. Rsync: `rsync -r --exclude="*_audio.wav" /home/erik/Experiments KTHStation:Experiments`
6. Link: `http://130.237.67.195:3000`
